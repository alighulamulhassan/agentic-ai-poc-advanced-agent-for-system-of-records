#!/usr/bin/env python3
"""
AWS CDK App — Enterprise Agent Infrastructure

Deploys three stacks:
  1. SecurityStack   — Cognito, WAF, Secrets Manager
  2. DataStack       — RDS PostgreSQL, ElastiCache Redis, OpenSearch
  3. AgentStack      — ECS Fargate, ALB, ECR, CloudWatch, X-Ray

Usage:
  pip install aws-cdk-lib constructs
  cdk bootstrap aws://ACCOUNT/REGION
  cdk deploy --all

Session for audience (Month 6 Lab):
  Deploy the DataStack first, then AgentStack.
  Walk through the CDK diff to understand what's being created.
"""
import aws_cdk as cdk
from agent_stack import AgentStack
from data_stack import DataStack
from security_stack import SecurityStack

app = cdk.App()

env = cdk.Environment(
    account=app.node.try_get_context("account") or "123456789012",
    region=app.node.try_get_context("region") or "us-east-1",
)

# Stack 1: Security (Cognito, WAF, Secrets)
security = SecurityStack(app, "AgentSecurityStack", env=env)

# Stack 2: Data (RDS, Redis, OpenSearch)
data = DataStack(app, "AgentDataStack", env=env)

# Stack 3: Application (ECS, ALB, CloudWatch)
agent = AgentStack(
    app, "AgentAppStack",
    db_secret=data.db_secret,
    vpc=data.vpc,
    env=env,
)
agent.add_dependency(security)
agent.add_dependency(data)

app.synth()
