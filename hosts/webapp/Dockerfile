FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    curl nmap net-tools iproute2 iputils-ping \
    openssh-server sshpass sudo \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir flask requests

WORKDIR /app
COPY vuln_app.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
