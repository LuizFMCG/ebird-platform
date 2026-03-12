# AWS bootstrap

This project is prepared for S3-first publication of curated app datasets. The Streamlit app itself is not hosted on S3 in the first phase.

## Verify local AWS CLI

```powershell
aws --version
aws configure list
aws sts get-caller-identity --profile ebird-admin
aws iam get-account-summary --profile ebird-admin
aws s3 ls --profile ebird-admin
```

## Configure credentials

```powershell
aws configure --profile ebird-admin
```

## Create the bucket in us-east-1

```powershell
aws s3api create-bucket --bucket <unique-bucket-name> --region us-east-1 --profile ebird-admin
aws s3api put-bucket-versioning --bucket <unique-bucket-name> --versioning-configuration Status=Enabled --profile ebird-admin
aws s3api put-bucket-encryption --bucket <unique-bucket-name> --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' --profile ebird-admin
aws s3api put-public-access-block --bucket <unique-bucket-name> --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true --profile ebird-admin
```

## Upload curated app artifacts

```powershell
aws s3 sync D:\ebird-platform\published s3://<unique-bucket-name>/published/ --profile ebird-admin
aws s3 ls s3://<unique-bucket-name>/published/ --recursive --profile ebird-admin
```
