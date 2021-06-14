FROM continuumio/miniconda:4.6.14

# Create non-root user 
ARG UID
ARG GID
RUN groupadd -g $GID -o otg
RUN useradd -m -u $UID -g $GID -o -s /bin/bash otg

# Do everything that requires root user
# Install OpenJDK-8 (as root)
RUN apt-get update && \
    apt-get install -y openjdk-8-jdk && \
    apt-get install -y ant && \
    apt-get clean;

# Fix certificate issues (as root)
RUN apt-get update && \
    apt-get install ca-certificates-java && \
    apt-get clean && \
    update-ca-certificates -f;

# Install parallel
RUN apt install -yf parallel

# download gcta
RUN apt-get install unzip
RUN wget https://cnsgenomics.com/software/gcta/bin/gcta_1.92.3beta3.zip -P /software/gcta
RUN chown -R otg:otg /software/gcta

# switch to otg user
USER otg

# Conda and the envirounment dependencies
COPY ./environment.yaml /home/otg/finemapping/
WORKDIR /home/otg/finemapping
RUN conda env create -n finemapping --file environment.yaml
RUN echo "source activate finemapping" > ~/.bashrc
ENV PATH /home/otg/.conda/envs/finemapping/bin:$PATH

# Setup JAVA_HOME -- useful for docker commandline
ENV JAVA_HOME /usr/lib/jvm/java-8-openjdk-amd64/
RUN export JAVA_HOME

# Install GCTA
RUN unzip /software/gcta/gcta_1.92.3beta3.zip -d /software/gcta
RUN rm /software/gcta/gcta_1.92.3beta3.zip
ENV PATH="/software/gcta/gcta_1.92.3beta3:${PATH}"

# Google Cloud SDK
RUN curl https://sdk.cloud.google.com | bash

# Default command
CMD ["/bin/bash"]

# Copy the v2d project
COPY ./ /home/otg/finemapping

# Make all files in finemapping owned by the non-root user
USER root
RUN chown -R otg:otg /home/otg/finemapping

# Run container as non-root user
USER otg
