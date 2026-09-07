from sa_dsl import (
    Appearance,
    GrpcServer,
    Golang,
    HttpServer,
    ServiceModule,
)

from processorder.project.processorder import project

analytics_service = project.service(
    'Analytics Service',
    appearance=Appearance(color='#05ABF7'),
    language=Golang(version='1.25.4'),
    module=ServiceModule(path='github.com/gorundebug/analyticsservice'),
    http_server=HttpServer(port=9093),
    grpc_server=GrpcServer(port=9203, default_timeout=0),
)

analytics_pipeline = analytics_service.pipeline('analytics')

analytics_sources_pipeline = analytics_service.pipeline('analyticsSources')

join_analytics_pipeline = analytics_service.pipeline('joinAnalytics')

multi_join_analytics_pipeline = analytics_service.pipeline('multiJoinAnalytics')

from processorder.services.analytics_service.pipelines import analytics as _analytics_pipeline

from processorder.services.analytics_service.pipelines import analytics_sources as _analytics_sources_pipeline

from processorder.services.analytics_service.pipelines import join_analytics as _join_analytics_pipeline

from processorder.services.analytics_service.pipelines import multi_join_analytics as _multi_join_analytics_pipeline

from processorder.services.analytics_service.pipelines.analytics_sources import analytics_shipments

from processorder.services.analytics_service.pipelines.analytics_sources import split_analytics_orders

from processorder.services.analytics_service.pipelines.analytics_sources import split_analytics_payments

from processorder.services.analytics_service.pipelines.join_analytics import key_orders_for_join

from processorder.services.analytics_service.pipelines.join_analytics import key_payments_for_join

from processorder.services.analytics_service.pipelines.multi_join_analytics import key_orders_for_multi_join

from processorder.services.analytics_service.pipelines.multi_join_analytics import key_payments_for_multi_join

from processorder.services.analytics_service.pipelines.multi_join_analytics import key_shipments_for_multi_join

split_analytics_orders >> key_orders_for_join

split_analytics_payments >> key_payments_for_join

split_analytics_orders >> key_orders_for_multi_join

split_analytics_payments >> key_payments_for_multi_join

analytics_shipments >> key_shipments_for_multi_join
