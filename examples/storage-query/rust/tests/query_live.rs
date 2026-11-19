//! Execute only against disposable stores created by the example Compose fixture.
use std::{sync::{Arc, Mutex}, time::Duration};
use servicelib::{MessageContext, runtime::{common::{CallableSubStream, SubStreamCollectorFunc},
    config::{CallSemantics, ConfigLoader}, environment::{RuntimeEnvironment, metrics::Metrics}}};
use storage_worker::internal::{app::Service, config::Config, types::{StorageRequest, StorageResult}};

async fn invoke(entry: Arc<dyn CallableSubStream<StorageRequest, StorageResult>>, key: &str, value: &[u8], id: &str) -> Vec<StorageResult> {
    let results = Arc::new(Mutex::new(Vec::new()));
    let output = results.clone();
    entry.consume(MessageContext::new().with_timeout_limit(Duration::from_secs(10)),
        StorageRequest { request_id: id.into(), key: key.into(), value: value.into() },
        Arc::new(SubStreamCollectorFunc(move |_, item: servicelib::Payload<StorageResult>| {
            let output = output.clone();
            async move {
                let done = item.kind == "completed";
                output.lock().unwrap().push((*item).clone());
                done
            }
        }))).await.expect("generated SubStream failed");
    let rows = results.lock().unwrap().clone();
    assert_eq!(rows.iter().filter(|r| r.kind == "completed").count(), 1);
    assert!(rows.iter().all(|r| r.request_id == id));
    rows
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore = "requires disposable PostgreSQL and S3 stores; run explicitly with --ignored"]
async fn live_generated_query_graph() {
    assert_eq!(std::env::var("SA_QUERY_DISPOSABLE").as_deref(), Ok("1"),
        "requires disposable Compose stores");
    let dsn = std::env::var("DATABASE_CONNECTION_STRING").unwrap();
    let pool = sqlx::PgPool::connect(&dsn).await.unwrap();
    sqlx::query("CREATE TABLE IF NOT EXISTS query_example_items (key text PRIMARY KEY, value bytea NOT NULL)").execute(&pool).await.unwrap();
    sqlx::query("TRUNCATE query_example_items").execute(&pool).await.unwrap();
    let shared = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let s3 = aws_sdk_s3::Client::from_conf(aws_sdk_s3::config::Builder::from(&shared)
        .endpoint_url(std::env::var("OBJECTS_ADDRESS").unwrap()).force_path_style(true).build());
    s3.create_bucket().bucket("query-example").send().await.unwrap();

    let metrics = Metrics::noop();
    let loader = ConfigLoader::load(None::<String>, None::<String>, Config::default(), &metrics, "StorageWorker").unwrap();
    let config = loader.current();
    let environment = RuntimeEnvironment::with_metrics(CallSemantics::FunctionCall, metrics).without_tracing();
    environment.publish_runtime_config(loader.runtime_config());
    let context = MessageContext::new();
    let service = Service::new(context.clone(), &config, environment, loader).await.unwrap();
    let runner = service.clone();
    let running = tokio::spawn(async move { runner.run(context).await.map_err(|error| error.to_string()) });
    tokio::time::timeout(Duration::from_secs(10), async {
        loop {
            if tokio::net::TcpStream::connect("127.0.0.1:8080").await.is_ok() { break; }
            assert!(!running.is_finished(), "service stopped during startup");
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    }).await.expect("generated service HTTP listener did not start");

    let key = "bound-'key";
    let returned = invoke(service.get_returning_request_substream(), "returning-'key", b"a\0b", "returning").await;
    assert_eq!(returned.iter().find(|r| r.kind == "record").unwrap().value, b"a\0b");
    let stored = invoke(service.get_rows_request_substream(), "returning-'key", b"", "returning-read").await;
    assert_eq!(stored.iter().find(|r| r.kind == "record").unwrap().value, b"a\0b");
    invoke(service.get_execute_request_substream(), key, b"value", "write").await;
    let rows = invoke(service.get_rows_request_substream(), key, b"", "read").await;
    assert_eq!(rows.iter().find(|r| r.kind == "record").unwrap().value, b"value");
    assert_eq!(invoke(service.get_rows_request_substream(), "absent", b"", "empty").await.len(), 1);
    invoke(service.get_put_object_request_substream(), "object", b"payload", "put").await;
    let object = invoke(service.get_get_object_request_substream(), "object", b"", "get").await;
    let bytes: Vec<u8> = object.iter().filter(|r| r.kind != "completed").flat_map(|r| r.value.clone()).collect();
    assert_eq!(bytes, b"payload");
    invoke(service.get_head_object_request_substream(), "object", b"", "head").await;
    let listing = invoke(service.get_list_objects_request_substream(), "object", b"", "list").await;
    assert!(listing.len() > 1);
    invoke(service.get_delete_object_request_substream(), "object", b"", "delete").await;
    assert!(s3.head_object().bucket("query-example").key("object").send().await.is_err());
    pool.close().await;
    // The generated runner uses process signals; this process is a disposable test container.
    assert!(std::process::Command::new("kill").args(["-TERM", &std::process::id().to_string()]).status().unwrap().success());
    tokio::time::timeout(Duration::from_secs(10), running).await.unwrap().unwrap().unwrap();
}
