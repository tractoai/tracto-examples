# Tracto.ai examples

Welcome to this guide on working with Tracto.ai Jupyter notebooks! These notebooks demonstrate how to use Tracto.ai functionality through practical examples.

## Overview

This repository contains example Jupyter notebooks showing different use cases and features of Tracto.ai:

- Machine learning examples using Tracto.ai and PyTorch
  - Training
  - Inference
- Data preparation and analysis
- Managing files, documents and tables
- Uploading and manipulating data
- Administration and management tasks

## Getting started

Please refer to the official Docker installation documentation: https://docs.docker.com/get-docker/

To run the example notebooks:

1. Clone repository `git clone https://github.com/tractoai/tracto-examples.git`
2. Set required environment variables in your shell (you need access to Tracto.ai platform):
   ```bash
   export YT_TOKEN=<your_token>
   export YT_PROXY=<proxy_address>
   ```
3. Run docker-compose from the repository root:
   ```bash
   docker-compose up
   ```
4. Open the provided Jupyter URL in your browser: http://localhost:8888
