import os
import time
import uuid
from typing import Iterable, Any

import yt.wrapper as yt

from orc_sdk.workflow import workflow
from orc_sdk.step import task


@task(retval_names=["table_path"])
def preprocess_data(table_path: str, working_dir: str) -> str:
    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())

    new_table_path = f"{working_dir}/data_preprocessed_{int(time.time())}"

    def mapper(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
        text_length = len(row["text"])
        if text_length > 42:
            yield row

    yt_client.run_map(
        mapper, table_path, new_table_path,
        spec={
            "secure_vault": {
                "docker_auth": {"username": "user", "password": yt_client.config["token"]}
            },
            "mapper": {
                "docker_image": os.environ["YT_BASE_LAYER"],
            }
        }
    )

    return new_table_path


@task()
def tune_llama(table_path: str, result_path: str, pool_tree_name: str):
    from tractorun.backend.tractorch import Tractorch
    from tractorun.run import run
    from tractorun.mesh import Mesh
    from tractorun.resources import Resources
    from tractorun.stderr_reader import StderrMode

    from example_tune.train import get_train_func

    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())
    working_dir = f"//tmp/examples/tractorun-tune-llama-{uuid.uuid4()}"
    yt_client.create("map_node", working_dir, recursive=True)

    train = get_train_func(table_path, result_path)

    run(
        train,
        backend=Tractorch(),
        yt_path=f"{working_dir}/working_dir",
        mesh=Mesh(node_count=1, process_per_node=8, gpu_per_process=1, pool_trees=[pool_tree_name]),
        resources=Resources(
            cpu_limit=100,
            memory_limit=858993459200,  # 800G
        ),
        proxy_stderr_mode=StderrMode.primary,
        yt_client=yt_client,
        yt_operation_spec={
            "secure_vault": {
                "docker_auth": {"username": "user", "password": yt_client.config["token"]}
            },
        }
    )


BASE_PATH = os.environ.get("WF_BASE_PATH", "//home/samples/orchestracto/demo-tune-llama")


@workflow(
    workflow_path=f"{BASE_PATH}/the_workflow",
)
def the_workflow(wfro):
    prep_data_step = wfro.register_first_step(
        preprocess_data("//home/samples/shakespeare", BASE_PATH)
        .with_id("preprocess_data")
        .with_secret(
            key="YT_TOKEN", value_src_type="secret_store",
            value_ref=f"{BASE_PATH}/secrets:my_token",
        )
    )

    (tune_llama(prep_data_step.outputs.table_path, f"{BASE_PATH}/result", "default_gpu_h100")
        .with_id("tune_llama")
        .with_secret(
            key="YT_TOKEN", value_src_type="secret_store",
            value_ref=f"{BASE_PATH}/secrets:my_token",
        )
        .with_base_image("cr.eu-north1.nebius.cloud/e00faee7vas5hpsh3s/orchestracto/example-llama-tune-step:1")
        .with_additional_requirements(["tractorun"])
     )
