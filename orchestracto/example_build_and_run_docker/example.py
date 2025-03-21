import datetime
import os
import subprocess
import tempfile

from orc_sdk import workflow, task, RawStep


BASE_PATH = os.environ.get("WF_BASE_PATH", "//home/samples/orchestracto/demo-build-run-docker")
TRACTO_REGISTRY_URL = os.environ["TRACTO_REGISTRY_URL"]


@task(retval_names=["docker_image"])
def build_docker(
        python_packages: list[str],
        registry_url: str,
        image_name: str = f"{BASE_PATH.removeprefix('//')}/registry/the-image",
        image_tag: str | None = None,
) -> str:
    BUILDAH_ENV = {
        "STORAGE_DRIVER": "vfs",
        "BUILDAH_FORMAT": "docker",
        "BUILDAH_ISOLATION": "chroot",
    }

    if image_tag is None:
        image_tag = datetime.datetime.now().strftime('%Y-%m-%d-%H-%M-%S')

    with tempfile.NamedTemporaryFile() as tf:
        with open(tf.name, "w") as f:
            f.write("FROM ubuntu:22.04\n")
            f.write("RUN apt-get update && apt-get install -y python3 python3-pip\n")
            f.write(f"RUN pip install -U {' '.join(python_packages)}\n")

        login_args = ["buildah", "login", "-u", "user", "-p", os.environ["YT_TOKEN"], registry_url]
        subprocess.check_call(login_args)

        full_tag = f"{registry_url}/{image_name}:{image_tag}"
        build_args = ["buildah", "build", "-f", tf.name, "-t", full_tag, "."]
        print("Build command:", " ".join(build_args))
        subprocess.check_call(build_args, env=BUILDAH_ENV)

        push_args = ["buildah", "push", full_tag]
        subprocess.check_call(push_args, env=BUILDAH_ENV)

    return full_tag


@workflow(
    workflow_path=f"{BASE_PATH}/the_workflow",
)
def the_workflow(wfro):
    build_docker_step = wfro.register_first_step(
        build_docker(
            ["requests==2.26.0", "ytsaurus-client", "ytsaurus-yson"],
            registry_url=TRACTO_REGISTRY_URL,
        )
        .with_id("build_docker")
        .with_secret(
            key="YT_TOKEN", value_src_type="secret_store",
            value_ref=f"{BASE_PATH}/secrets:my_token",
        )
        .with_base_image("quay.io/buildah/stable:v1.38.0")
        .with_cache()
    )

    build_docker_step >> RawStep(
        step_id="run_docker",
        task_type="docker",
        task_params={
            "docker_image": build_docker_step.outputs.docker_image,
            "command": "python3 -c 'import json, requests; print(json.dumps({\"requests_version\": requests.__version__}))' >&2",
        }
    ).with_secret(
        key="YT_TOKEN", value_src_type="secret_store",
        value_ref=f"{BASE_PATH}/secrets:my_token",
    ).with_output("requests_version")
