FROM mcr.microsoft.com/dotnet/sdk:5.0

COPY . /usr/local/src/restler-fuzzer

RUN apt-get update && \
    apt-get install -y python3 && \
    rm -fR /var/lib/apt/lists/* && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3 0 && \
    python3 /usr/local/src/restler-fuzzer/build-restler.py --repository_root_dir /usr/local/src/restler-fuzzer --dest_dir /opt

ENTRYPOINT [ "/opt/restler/Restler" ]

WORKDIR /mnt
