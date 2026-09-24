FROM public.ecr.aws/docker/library/python@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

COPY scanner-deps-hashed.txt /tmp/scanner-deps-hashed.txt
RUN python -m pip install --no-cache-dir --require-hashes \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    -r /tmp/scanner-deps-hashed.txt

COPY skillspector-2.11.2-py3-none-any.whl /tmp/skillspector-2.11.2-py3-none-any.whl
RUN python -m pip install --no-cache-dir --no-deps \
    /tmp/skillspector-2.11.2-py3-none-any.whl \
    && rm -f /tmp/scanner-deps-hashed.txt /tmp/skillspector-2.11.2-py3-none-any.whl

ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /scan
ENTRYPOINT ["skillspector"]
