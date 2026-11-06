package main

import (
	"os"
	"path/filepath"
	"reflect"
	"testing"
)

func TestMakersHelpersAndMultipleBusinessOwners(t *testing.T) {
	t.Setenv("GOWORK", "off")
	root := t.TempDir()
	files := map[string]string{
		"go.mod":         "module fixture\n\ngo 1.25.0\n",
		"svc/api/api.go": `package api; type Stream interface { Consume(int) }`,
		"svc/internal/functions/work/work.go": `package work
 import "fixture/svc/api"
 import "fixture/shared"
 type First struct { Stream api.Stream }
 func (f *First) Process() { helper(f.Stream) }
 func helper(s api.Stream) { invoke(func(){shared.Invoke(s,1)}) }
 func invoke(f func()) { f() }
 type Second struct { Other api.Stream }
 func (f *Second) Process() { f.Other.Consume(2) }
 // Recursion must terminate during analysis.
 func recursive(s api.Stream, n int) { if n>0 { recursive(s,n-1) }; s.Consume(n) }
 func Unowned(s api.Stream) { recursive(s,1) }
 `,
		// This local helper is imported but is outside the ./svc/... pattern.
		"shared/invoke.go": `package shared
 import "fixture/svc/api"
 func Invoke(s api.Stream, n int) { s.Consume(n) }
 `,
		"svc/internal/app/substreams.generated.go": `package app
 import "fixture/svc/api"
 type Service struct{}
 type a struct{}; func(a) Consume(int){}
 type b struct{}; func(b) Consume(int){}
 type c struct{}; func(c) Consume(int){}
 func(*Service) Alpha() api.Stream { return a{} }
 func(*Service) Beta() api.Stream { return b{} }
 func(*Service) Orphan() api.Stream { return c{} }
 `,
		"svc/internal/app/makers.go": `package app
 import "fixture/svc/internal/functions/work"
 func Makers(s *Service, choose bool) (*work.First,*work.Second) {
   first:=func()*work.First{return &work.First{Stream:s.Alpha()}}
   second:=&work.Second{Other:s.Beta()}
   if choose {second.Other=s.Alpha()}
   return first(),second
 }
 func NoBusiness(s *Service){work.Unowned(s.Orphan())}
 `,
	}
	for name, body := range files {
		p := filepath.Join(root, name)
		if err := os.MkdirAll(filepath.Dir(p), 0700); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	request := Request{Root: root, ServiceDirectory: filepath.Join(root, "svc"), Patterns: []string{"./svc/..."}, Business: []Business{
		{"first", filepath.Join(root, "svc/internal/functions/work"), []string{"First"}},
		{"firstReused", filepath.Join(root, "svc/internal/functions/work"), []string{"First"}},
		{"second", filepath.Join(root, "svc/internal/functions/work"), []string{"Second"}},
	}, Substreams: []Substream{{"alpha", []string{"Alpha"}}, {"beta", []string{"Beta"}}, {"orphan", []string{"Orphan"}}, {"absent", []string{"Absent"}}}}
	result, err := analyze(request)
	if err != nil {
		t.Fatal(err)
	}
	got := [][2]string{}
	for _, link := range result.Links {
		got = append(got, [2]string{link.Source, link.Target})
		if len(link.Chain) < 2 {
			t.Fatalf("missing evidence: %+v", link)
		}
		for _, step := range link.Chain {
			if step.Line < 1 || step.File == "" || filepath.IsAbs(step.File) {
				t.Fatalf("invalid location: %+v", step)
			}
		}
	}
	want := [][2]string{{"first", "alpha"}, {"firstReused", "alpha"}, {"second", "alpha"}, {"second", "beta"}}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("got %v, want %v", got, want)
	}
	if !reflect.DeepEqual(result.Unresolved, []string{"absent"}) {
		t.Fatal(result.Unresolved)
	}
	// With no model business functions, even valid concrete calls produce no links.
	request.Business = nil
	result, err = analyze(request)
	if err != nil {
		t.Fatal(err)
	}
	if len(result.Links) != 0 {
		t.Fatal(result.Links)
	}
}
