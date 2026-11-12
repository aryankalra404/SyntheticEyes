# Renders one draft frame of scene.blend on CPU with the pinned Blender, as a smoke test.
#
#   docker build --platform linux/amd64 -t syntheticeyes .
#   docker run --rm --platform linux/amd64 -v "$PWD/outputs/docker:/work/outputs/docker" syntheticeyes
#
# Output: outputs/docker/draft.png (eyes at centre, EEVEE draft, 512x512).
# Blender only ships x86_64 Linux builds, so on Apple Silicon this runs under emulation.
# EEVEE needs an OpenGL context: Xvfb plus Mesa's llvmpipe provide one on the CPU.
# Any other wrapper command works the same way, e.g.
#   docker run --rm --platform linux/amd64 -v "$PWD/outputs:/work/outputs" syntheticeyes \
#     blender -b scene.blend -P wrapper/eyes.py -- --input left --quality draft

FROM ubuntu:24.04

ARG BLENDER_VERSION=4.5.1
ARG BLENDER_SHA256=085a7ed4ed80c3cb66783bad76f236f39897de5d33884abd133e0c6db94c0f14

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl xz-utils \
        libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libxkbcommon-x11-0 \
        libsm6 libice6 libgl1 libegl1 libgl1-mesa-dri libglu1-mesa \
        xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/blender.tar.xz \
        "https://download.blender.org/release/Blender${BLENDER_VERSION%.*}/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
    && echo "${BLENDER_SHA256}  /tmp/blender.tar.xz" | sha256sum -c - \
    && mkdir /opt/blender \
    && tar -xJf /tmp/blender.tar.xz -C /opt/blender --strip-components=1 \
    && rm /tmp/blender.tar.xz \
    && ln -s /opt/blender/blender /usr/local/bin/blender

WORKDIR /work
COPY . /work

# A virtual display for EEVEE. Started directly: xvfb-run hangs when it is PID 1.
ENV DISPLAY=:99
RUN printf '#!/bin/sh\nXvfb :99 -screen 0 1280x1024x24 -nolisten tcp >/dev/null 2>&1 &\nsleep 1\nexec "$@"\n' \
        > /usr/local/bin/with-display && chmod +x /usr/local/bin/with-display
ENTRYPOINT ["/usr/local/bin/with-display"]

CMD ["blender", "-b", "scene.blend", "-P", "wrapper/eyes.py", "--", \
     "--move", "0", "0", "--quality", "draft", "--out", "outputs/docker/draft.png"]
