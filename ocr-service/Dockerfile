# GPU service. Base image must match the host CUDA driver; PaddleOCR-VL's official guide recommends the
# vendor image (see https://www.paddleocr.ai). Replace BASE with the image you validated on your GPU.
ARG BASE=ccr-2vdh3abv-pub.cnb.cool/paddlepaddle/paddleocr/paddleocr-vl:latest
FROM ${BASE}
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV OCR_SERVICE_AUTOSTART=1 PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8090"]
