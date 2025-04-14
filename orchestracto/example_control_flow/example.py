import os

from orc_sdk import workflow, task, each


BASE_PATH = os.environ.get("WF_BASE_PATH")


@task(retval_names=["value"])
def multiplier(value: int, multiplier: int = 10) -> int:
    return value * multiplier


@task(retval_names=["value"])
def adder(value: int, to_add: int = 1) -> int:
    return value + to_add


@workflow(
    workflow_path=f"{BASE_PATH}/wf_example_control_flow",
)
def the_workflow(wfro):
    mp_step = multiplier(each).for_each([1, 2, 3, 4, 5])
    wfro.register_first_step(mp_step)

    mp_step >> adder(each, 3).for_each(mp_step.outputs.value)
