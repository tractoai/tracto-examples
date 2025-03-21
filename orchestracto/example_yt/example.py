import os
import random
import uuid
from typing import Any, Iterable

import yt.wrapper as yt

from orc_sdk import workflow, task


@task(retval_names=["table_path"])
def generate_table(dir_path: str) -> str:
    table_path = f"{dir_path}/table_{uuid.uuid4()}"
    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())
    yt_client.create("table", table_path)
    yt_client.write_table(
        table_path,
        [{"id": str(uuid.uuid4()), "value": random.randint(0, 1000)} for i in range(100)]
    )
    return table_path


@task(retval_names=["table_path"])
def add_random_value(table_path: str) -> str:
    def mapper(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
        row["value"] = row["value"] + random.randint(0, 100)
        yield row

    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())
    yt_client.config["pickling"]["pickler_kwargs"] = [{"key": "recurse", "value": True}]
    yt_client.run_map(
        mapper, table_path, table_path,
        spec={
            "secure_vault": {
                "docker_auth": {"username": "user", "password": yt_client.config["token"]}
            },
            "mapper": {
                "docker_image": os.environ["YT_BASE_LAYER"],
            }
        }
    )

    return table_path


@task(retval_names=["table_path"])
def filter_values(table_path: str, threshold: int) -> str:
    def mapper(row: dict[str, Any]) -> Iterable[dict[str, Any]]:
        if row["value"] > threshold:
            yield row

    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())
    yt_client.config["pickling"]["pickler_kwargs"] = [{"key": "recurse", "value": True}]
    yt_client.run_map(
        mapper, table_path, table_path,
        spec={
            "secure_vault": {
                "docker_auth": {"username": "user", "password": yt_client.config["token"]}
            },
            "mapper": {
                "docker_image": os.environ["YT_BASE_LAYER"],
            }
        }
    )

    return table_path


@task()
def merge_tables(table_1_path: str, table_2_path: str):
    yt_client = yt.YtClient(config=yt.default_config.get_config_from_env())
    yt_client.run_merge([table_1_path, table_2_path], f"{table_1_path}_merged")


BASE_PATH = os.environ.get("WF_BASE_PATH", "//home/samples/orchestracto/demo-yt")


@workflow(
    f"{BASE_PATH}/the_workflow",
)
def the_workflow(wfro):
    working_dir = BASE_PATH

    secret_data = dict(
        key="YT_TOKEN", value_src_type="secret_store",
        value_ref=f"{BASE_PATH}/secrets:my_token",
    )

    gen_table_1_step = generate_table(working_dir).with_secret(**secret_data).with_memory_limit(512 * 1024 * 1024)
    wfro.register_first_step(gen_table_1_step)

    table_1_rand_val_step = add_random_value(gen_table_1_step.outputs.table_path).with_secret(**secret_data)

    gen_table_2_step = generate_table(working_dir).with_secret(**secret_data)
    wfro.register_first_step(gen_table_2_step)

    table_2_rand_val_step = filter_values(gen_table_2_step.outputs.table_path, 500).with_secret(**secret_data)

    merge_tables(
        table_1_rand_val_step.outputs.table_path,
        table_2_rand_val_step.outputs.table_path
    ).with_secret(**secret_data).with_additional_requirements(["requests==2.25.1"])
