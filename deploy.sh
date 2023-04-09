docker build -t me/python-stripped:latest -f Dockerfile.stripped-python .
docker build -t me/python-gpapi:latest -f Dockerfile.gpapi .
. .envServer
docker build --build-arg authSubToken=$authSubToken --build-arg gsfId=$gsfId -t me/update-tracker:latest .
docker run -d -v /root/persist:/persist --name update-tracker me/update-tracker
