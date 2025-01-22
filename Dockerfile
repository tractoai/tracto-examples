FROM jupyter/base-notebook

RUN pip install -U tractorun ytsaurus-client ytsaurus-yson torch torchvision transformers peft trl datasets

USER root
