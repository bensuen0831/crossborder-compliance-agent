from __future__ import annotations
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

def configure_tracing(service_name: str, console_export: bool = False) -> None:
    provider=TracerProvider(resource=Resource.create({"service.name":service_name}))
    if console_export: provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
