"""
Data Stack — RDS PostgreSQL, ElastiCache Redis, OpenSearch.

Provisions:
  - VPC with public/private/isolated subnets
  - RDS Aurora PostgreSQL Serverless v2 (replaces SQLite)
  - ElastiCache Redis (session state, HITL approval cache)
  - OpenSearch (replaces ChromaDB for production RAG)
  - S3 bucket (document storage)

Session for audience (Month 6 Lab):
  TODO: Add a DynamoDB table for HITL approval state so approvals
  survive Lambda cold starts and can be queried by approval_id.
  Table: AgentHITLApprovals (PK: approval_id, GSI: conversation_id)
"""
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_rds as rds
import aws_cdk.aws_elasticache as elasticache
import aws_cdk.aws_opensearchservice as opensearch
import aws_cdk.aws_s3 as s3
import aws_cdk.aws_secretsmanager as secretsmanager
from constructs import Construct


class DataStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------
        # VPC
        # -------------------------------------------------------
        self.vpc = ec2.Vpc(
            self, "AgentVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24,
                ),
            ],
        )

        # -------------------------------------------------------
        # RDS Aurora PostgreSQL Serverless v2
        # (scales to zero when idle — cost-effective for labs)
        # -------------------------------------------------------
        db_security_group = ec2.SecurityGroup(
            self, "DBSecurityGroup",
            vpc=self.vpc,
            description="Allow agent ECS tasks to connect to RDS",
        )

        self.db_secret = rds.DatabaseSecret(
            self, "DBSecret",
            username="agentadmin",
            secret_name="/agent/db-credentials",
        )

        self.db_cluster = rds.DatabaseCluster(
            self, "AgentDB",
            engine=rds.DatabaseClusterEngine.aurora_postgres(
                version=rds.AuroraPostgresEngineVersion.VER_15_4
            ),
            credentials=rds.Credentials.from_secret(self.db_secret),
            serverless_v2_min_capacity=0.5,
            serverless_v2_max_capacity=4.0,
            writer=rds.ClusterInstance.serverless_v2("writer"),
            readers=[
                rds.ClusterInstance.serverless_v2("reader", scale_with_writer=True),
            ],
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
            security_groups=[db_security_group],
            backup=rds.BackupProps(retention=cdk.Duration.days(7)),
            deletion_protection=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
            default_database_name="agentdb",
        )

        # -------------------------------------------------------
        # ElastiCache Redis — session state + HITL cache
        # -------------------------------------------------------
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Redis subnet group",
            subnet_ids=[s.subnet_id for s in self.vpc.isolated_subnets],
        )

        redis_sg = ec2.SecurityGroup(
            self, "RedisSG",
            vpc=self.vpc,
            description="Redis security group",
        )

        self.redis = elasticache.CfnReplicationGroup(
            self, "AgentRedis",
            replication_group_description="Agent session cache",
            cache_node_type="cache.t4g.small",
            engine="redis",
            engine_version="7.0",
            num_cache_clusters=2,
            automatic_failover_enabled=True,
            at_rest_encryption_enabled=True,
            transit_encryption_enabled=True,
            cache_subnet_group_name=redis_subnet_group.ref,
            security_group_ids=[redis_sg.security_group_id],
        )

        # -------------------------------------------------------
        # OpenSearch — production RAG vector store
        # -------------------------------------------------------
        self.opensearch_domain = opensearch.Domain(
            self, "AgentSearch",
            version=opensearch.EngineVersion.OPENSEARCH_2_11,
            capacity=opensearch.CapacityConfig(
                data_node_instance_type="t3.small.search",
                data_nodes=1,                  # increase for production HA
            ),
            ebs=opensearch.EbsOptions(
                enabled=True,
                volume_size=20,
                volume_type=ec2.EbsDeviceVolumeType.GP3,
            ),
            vpc=self.vpc,
            vpc_subnets=[ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS)],
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            node_to_node_encryption=True,
            enforce_https=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # -------------------------------------------------------
        # S3 — document storage for RAG
        # -------------------------------------------------------
        self.documents_bucket = s3.Bucket(
            self, "DocumentsBucket",
            bucket_name=f"agent-documents-{self.account}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=cdk.Duration.days(30),
                        )
                    ]
                )
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # -------------------------------------------------------
        # Outputs
        # -------------------------------------------------------
        cdk.CfnOutput(self, "VpcId", value=self.vpc.vpc_id)
        cdk.CfnOutput(self, "DBClusterEndpoint", value=self.db_cluster.cluster_endpoint.hostname)
        cdk.CfnOutput(self, "DBSecretArn", value=self.db_secret.secret_arn)
        cdk.CfnOutput(self, "OpenSearchEndpoint", value=self.opensearch_domain.domain_endpoint)
        cdk.CfnOutput(self, "DocumentsBucket", value=self.documents_bucket.bucket_name)
