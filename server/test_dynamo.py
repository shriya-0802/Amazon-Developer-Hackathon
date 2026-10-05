"""Test DynamoDB access with existing AWS credentials"""
import boto3
import os
from dotenv import load_dotenv
load_dotenv()

try:
    dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
    client = boto3.client('dynamodb', region_name=os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))
    
    # List existing tables
    tables = client.list_tables()
    print("✅ DynamoDB connection successful!")
    print(f"Existing tables: {tables['TableNames']}")
    
except Exception as e:
    print(f"❌ Error: {e}")
