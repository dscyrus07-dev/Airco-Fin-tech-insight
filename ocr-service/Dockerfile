# GPU service. Validated on an RTX 3060 12 GB (see docs/ocr/R5_DEVIN_REPORT.md): CUDA 12.6 runtime +
# paddlepaddle-gpu 3.3.1 (cu126 wheels) + paddleocr[doc-parser] 3.7.0. The base image must match the host driver.
# The PaddleOCR vendor image is an alternative: build with --build-arg BASE=<image> and drop the apt/pip steps.
ARG BASE=nvidia/cuda:12.6.2-runtime-ubuntu22.04
FROM ${BASE}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-dev libglib2.0-0 libgl1 libsm6 libxext6 libxrender1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip3 install --no-cache-dir --timeout 120 \
      -i https://www.paddlepaddle.org.cn/packages/stable/cu126/ --extra-index-url https://pypi.org/simple \
      paddlepaddle-gpu==3.3.1 && pip3 install --no-cache-dir --timeout 120 -r requirements.txt
COPY app.py .
ENV OCR_SERVICE_AUTOSTART=1 PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
