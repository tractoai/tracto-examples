import os
import random
import signal
import sys
import time

from orc_sdk import workflow, task


@task()
def foo(an_arg: str = "hello") -> str:
    print("I am foo step")
    if random.random() > 0.5:
        raise RuntimeError("Random error in foo")
    return f"{an_arg} from foo"


@task(retval_names=["some_output", "another_output"])
def bar(aaa: int, bbb: str) -> tuple[str, str]:
    print("bar got arg:", aaa)
    return "bar-" + bbb, "hallo"


@task()
def clever_printer(msg: str, additional_msg: str) -> int:
    def exiter(signum, frame):
        print("Got signal", signum)
        for i in range(10, 0, -1):
            print("Exiting in", i)
            time.sleep(1)
        sys.exit(0)

    signal.signal(signal.SIGTERM, exiter)

    print("Clever printer got message:", msg)
    print("Additional message:", additional_msg)

    for _ in range(40):
        print("Sleeping...")
        time.sleep(3)

    return 1337


BASE_PATH = os.environ.get("WF_BASE_PATH", "//home/samples/orchestracto/demo-dummy")


@workflow(
    f"{BASE_PATH}/the_workflow",
    triggers=[],
)
def the_workflow(wfro, my_param: str = "hello"):
    foo_step = foo(an_arg=my_param).with_retries(10)
    wfro.register_first_step(foo_step)

    bar_step = bar(42, bbb=foo_step.outputs.output_1).with_id("st2_1")
    clever_printer_step = clever_printer(bar_step.outputs.some_output, bar_step.outputs.another_output).with_id("st3")

    foo_step >> [bar_step, bar(37, "aaa")] >> clever_printer_step
