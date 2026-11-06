// Read-only Go call analysis. Architecture identities come from the Python model.
// VTA supplies possible dynamic callees; this is not a runtime execution trace.
package main

import (
	"encoding/json"
	"fmt"
	"go/types"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"golang.org/x/tools/go/callgraph"
	"golang.org/x/tools/go/callgraph/vta"
	"golang.org/x/tools/go/packages"
	"golang.org/x/tools/go/ssa"
	"golang.org/x/tools/go/ssa/ssautil"
)

type Business struct {
	Key       string   `json:"key"`
	Directory string   `json:"directory"`
	Symbols   []string `json:"symbols"`
}
type Substream struct {
	Key     string   `json:"key"`
	Symbols []string `json:"symbols"`
}
type Request struct {
	Root             string      `json:"root"`
	ServiceDirectory string      `json:"serviceDirectory"`
	Patterns         []string    `json:"patterns"`
	Business         []Business  `json:"business"`
	Substreams       []Substream `json:"substreams"`
}
type Step struct {
	Symbol string `json:"symbol"`
	File   string `json:"file"`
	Line   int    `json:"line"`
	Column int    `json:"column"`
}
type Link struct {
	Source string `json:"source"`
	Target string `json:"target"`
	Chain  []Step `json:"chain"`
}
type Result struct {
	Links      []Link   `json:"links"`
	Unresolved []string `json:"unresolved"`
}

func named(t types.Type) *types.Named {
	if p, ok := types.Unalias(t).(*types.Pointer); ok {
		t = p.Elem()
	}
	n, _ := types.Unalias(t).(*types.Named)
	return n
}
func contains(values []string, value string) bool {
	for _, v := range values {
		if v == value {
			return true
		}
	}
	return false
}
func inside(root, file string) bool {
	rel, err := filepath.Rel(root, file)
	return err == nil && rel != ".." && !strings.HasPrefix(rel, ".."+string(filepath.Separator)) && !filepath.IsAbs(rel)
}

func analyze(req Request) (Result, error) {
	result := Result{Links: []Link{}, Unresolved: []string{}}
	pkgs, err := packages.Load(&packages.Config{Dir: req.Root, Mode: packages.LoadSyntax}, req.Patterns...)
	if err != nil {
		return result, err
	}
	// Helpers in other local modules also carry interface values and calls.
	// Load their bodies without expanding SSA to the SDK and all third-party code.
	initial := map[string]bool{}
	for _, p := range pkgs {
		initial[p.PkgPath] = true
	}
	var localDependencies []string
	packages.Visit(pkgs, func(p *packages.Package) bool {
		if !initial[p.PkgPath] && len(p.GoFiles) > 0 && inside(req.Root, p.GoFiles[0]) {
			localDependencies = append(localDependencies, p.PkgPath)
		}
		return true
	}, nil)
	if len(localDependencies) > 0 {
		sort.Strings(localDependencies)
		patterns := append(append([]string(nil), req.Patterns...), localDependencies...)
		pkgs, err = packages.Load(&packages.Config{Dir: req.Root, Mode: packages.LoadSyntax}, patterns...)
		if err != nil {
			return result, err
		}
	}
	var loadErrors []string
	packages.Visit(pkgs, nil, func(p *packages.Package) {
		for _, e := range p.Errors {
			if len(loadErrors) < 8 {
				loadErrors = append(loadErrors, e.Error())
			}
		}
	})
	if len(loadErrors) > 0 {
		return result, fmt.Errorf("Go project cannot be analyzed: %s", strings.Join(loadErrors, "\n"))
	}
	prog, _ := ssautil.Packages(pkgs, ssa.InstantiateGenerics)
	prog.Build()
	funcs := ssautil.AllFunctions(prog)
	position := func(f *ssa.Function) Step {
		p := prog.Fset.Position(f.Pos())
		rel, _ := filepath.Rel(req.Root, p.Filename)
		return Step{f.String(), filepath.ToSlash(rel), p.Line, p.Column}
	}
	business := map[*ssa.Function][]string{}
	for f := range funcs {
		if f.Parent() != nil || f.Synthetic != "" {
			continue
		}
		p := prog.Fset.Position(f.Pos())
		name := f.Name()
		if recv := f.Signature.Recv(); recv != nil {
			if n := named(recv.Type()); n != nil {
				name = n.Obj().Name()
			}
		}
		for _, b := range req.Business {
			if filepath.Clean(filepath.Dir(p.Filename)) == filepath.Clean(b.Directory) && contains(b.Symbols, name) {
				business[f] = append(business[f], b.Key)
			}
		}
	}
	// Resolve the accessor's actual returned type, never infer identity from the
	// SubStream input/output types (multiple targets may share that signature).
	targets := map[string][]*ssa.Function{}
	for _, sub := range req.Substreams {
		for f := range funcs {
			if !contains(sub.Symbols, f.Name()) || f.Signature.Recv() == nil {
				continue
			}
			recv := named(f.Signature.Recv().Type())
			if recv == nil || recv.Obj().Name() != "Service" {
				continue
			}
			if filepath.Dir(prog.Fset.Position(f.Pos()).Filename) != filepath.Join(req.ServiceDirectory, "internal", "app") {
				continue
			}
			for _, block := range f.Blocks {
				for _, inst := range block.Instrs {
					ret, ok := inst.(*ssa.Return)
					if !ok {
						continue
					}
					for _, value := range ret.Results {
						if box, ok := value.(*ssa.MakeInterface); ok {
							value = box.X
						} else {
							continue
						}
						method := types.NewMethodSet(value.Type()).Lookup(nil, "Consume")
						if method != nil {
							targets[sub.Key] = append(targets[sub.Key], prog.MethodValue(method))
						}
					}
				}
			}
		}
		if len(targets[sub.Key]) == 0 {
			result.Unresolved = append(result.Unresolved, sub.Key)
		}
	}
	graph := vta.CallGraph(funcs, nil)
	allowed := func(f *ssa.Function) bool {
		file := prog.Fset.Position(f.Pos()).Filename
		if f.Synthetic != "" && file == "" {
			return true
		} // compiler method wrappers
		return inside(req.Root, file) && !strings.HasSuffix(file, ".generated.go") && !strings.HasSuffix(file, "_test.go")
	}
	type visit struct {
		node  *callgraph.Node
		chain []Step
	}
	unique := map[string]Link{}
	for target, functions := range targets {
		queue := []visit{}
		for _, f := range functions {
			if n := graph.Nodes[f]; n != nil {
				queue = append(queue, visit{n, []Step{position(f)}})
			}
		}
		seen := map[*callgraph.Node]bool{}
		for len(queue) > 0 {
			current := queue[0]
			queue = queue[1:]
			if seen[current.node] {
				continue
			}
			seen[current.node] = true
			if roots := business[current.node.Func]; len(roots) > 0 {
				for _, root := range roots {
					key := root + "\x00" + target
					if _, ok := unique[key]; !ok {
						unique[key] = Link{root, target, current.chain}
					}
				}
				continue // never cross a business-function boundary
			}
			incoming := append([]*callgraph.Edge(nil), current.node.In...)
			sort.Slice(incoming, func(i, j int) bool { return incoming[i].Caller.Func.String() < incoming[j].Caller.Func.String() })
			for _, edge := range incoming {
				caller := edge.Caller.Func
				if caller == nil || !allowed(caller) {
					continue
				}
				chain := current.chain
				if p := prog.Fset.Position(edge.Pos()); p.IsValid() {
					rel, _ := filepath.Rel(req.Root, p.Filename)
					chain = append([]Step{{caller.String(), filepath.ToSlash(rel), p.Line, p.Column}}, chain...)
				}
				queue = append(queue, visit{edge.Caller, chain})
			}
		}
	}
	for _, link := range unique {
		result.Links = append(result.Links, link)
	}
	sort.Slice(result.Links, func(i, j int) bool {
		a, b := result.Links[i], result.Links[j]
		if a.Source != b.Source {
			return a.Source < b.Source
		}
		return a.Target < b.Target
	})
	sort.Strings(result.Unresolved)
	return result, nil
}

func main() {
	var req Request
	if err := json.NewDecoder(os.Stdin).Decode(&req); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	result, err := analyze(req)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := json.NewEncoder(os.Stdout).Encode(result); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
