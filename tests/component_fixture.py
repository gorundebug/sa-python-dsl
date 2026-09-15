"""A small valid topology with two concrete repetitions of pricing logic."""
from sa_dsl import Project, Golang, ServiceModule, Function, Package
from sa_dsl.model import Service, Stream


def component_project() -> tuple[Project, Service, list[tuple[Stream, Stream]]]:
    project = Project('Components')
    service = project.service('Booking', language=Golang(), module=ServiceModule(path='example.com/booking'))
    amount = project.int_type('Amount', public_type=False)
    connector = project.custom_connector('Requests')
    fragments: list[tuple[Stream, Stream]] = []
    for name in ('Create', 'Update'):
        endpoint = connector.endpoint(name, function=Function('MakeRequest' + name, Package('requests')))
        output = connector.endpoint(name + ' Output', function=Function('MakeOutput' + name, Package('requests')))
        pipeline = service.pipeline(name)
        source = pipeline.input(name + ' Request', endpoint=endpoint, value_type=amount)
        load = pipeline.map(name + ' Load', function=Function('LoadCustomer', Package('pricing')), value_type=amount)
        price = pipeline.map(name + ' Price', function=Function('CalculatePrice', Package('pricing')), value_type=amount)
        sink = pipeline.sink(name + ' Response', endpoint=output, value_type=amount)
        source >> load >> price >> sink
        fragments.append((load, price))
    return project, service, fragments
