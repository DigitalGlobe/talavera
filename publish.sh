bucket=$1
name=$2

rm -r build
rm dist.zip
docker run --rm -it -v $(pwd):/app quay.io/pypa/manylinux1_x86_64 /app/scripts/build.sh
rm -r build/numpy*
touch build/google/__init__.py
zip -r -9 dist.zip README.md
cd src && zip -r9 ../dist.zip *.py && cd ..
cd build  && zip -r9 ../dist.zip * && cd ..
aws s3 cp dist.zip s3://$bucket/$name.zip --acl public-read
echo "https://s3.amazonaws.com/$bucket/$name.zip"
