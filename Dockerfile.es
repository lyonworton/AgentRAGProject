FROM elasticsearch:8.12.0
RUN bin/elasticsearch-plugin install --batch https://github.com/infinilabs/analysis-ik/releases/download/v8.12.0/elasticsearch-analysis-ik-8.12.0.zip || \
    bin/elasticsearch-plugin install --batch https://release.infinilabs.com/analysis-ik/stable/elasticsearch-analysis-ik-8.12.0.zip || \
    true