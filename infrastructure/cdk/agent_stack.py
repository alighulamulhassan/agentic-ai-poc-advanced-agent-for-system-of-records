"""
Agent Stack — ECS Fargate service, ALB, ECR, CloudWatch, X-Ray.

Provisions:
  - ECR repository for Docker image
  - ECS Cluster + Fargate Service (2 tasks, auto-scaling)
  - Application Load Balancer (HTTPS)
  - CloudWatch log group + dashboard
  - X-Ray daemon sidecar
  - IAM roles (least-privilege: Bedrock, Secrets Manager, S3, SNS)
  - EventBridge rule for HITL SNS → Lambda approval workflow

Session for audience (Month 6 Lab):
  TODO: Add auto-scaling policy based on agent_requests_total metric:
    - Scale up when p99 latency > 3s or error rate > 5%
    - Scale down when CPU < 20% for 10 minutes
"""
import aws_cdk as cdk
import aws_cdk.aws_ec2 as ec2
import aws_cdk.aws_ecr as ecr
import aws_cdk.aws_ecs as ecs
import aws_cdk.aws_ecs_patterns as ecs_patterns
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
import aws_cdk.aws_secretsmanager as secretsmanager
import aws_cdk.aws_sns as sns
from constructs import Construct


class AgentStack(cdk.Stack):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        db_secret: secretsmanager.ISecret,
        vpc: ec2.IVpc,
        **kwargs,
    ):
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------
        # ECR Repository
        # -------------------------------------------------------
        self.ecr_repo = ecr.Repository(
            self, "AgentECR",
            repository_name="enterprise-agent",
            lifecycle_rules=[
                ecr.LifecycleRule(max_image_count=10),
            ],
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # -------------------------------------------------------
        # CloudWatch Log Group
        # -------------------------------------------------------
        log_group = logs.LogGroup(
            self, "AgentLogs",
            log_group_name="/agent/application",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        decision_log_group = logs.LogGroup(
            self, "DecisionLogs",
            log_group_name="/agent/decisions",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # -------------------------------------------------------
        # IAM Task Role — least-privilege
        # -------------------------------------------------------
        task_role = iam.Role(
            self, "AgentTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AWSXRayDaemonWriteAccess"),
            ],
        )

        # Bedrock access (production LLM)
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
            resources=["arn:aws:bedrock:*::foundation-model/anthropic.*"],
        ))

        # Secrets Manager — read only our secrets
        task_role.add_to_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=[
                f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:/agent/*",
            ],
        ))

        # SNS — for HITL notifications
        hitl_topic = sns.Topic(
            self, "HITLTopic",
            topic_name="agent-hitl-approvals",
            display_name="Agent HITL Approval Requests",
        )
        hitl_topic.grant_publish(task_role)

        # -------------------------------------------------------
        # ECS Cluster
        # -------------------------------------------------------
        cluster = ecs.Cluster(
            self, "AgentCluster",
            vpc=vpc,
            container_insights=True,
        )

        # -------------------------------------------------------
        # Fargate Service + ALB
        # -------------------------------------------------------
        self.service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "AgentService",
            cluster=cluster,
            cpu=1024,          # 1 vCPU
            memory_limit_mib=2048,
            desired_count=2,   # 2 tasks for HA
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_ecr_repository(self.ecr_repo, tag="latest"),
                container_port=8000,
                task_role=task_role,
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="agent",
                    log_group=log_group,
                ),
                environment={
                    "ENVIRONMENT": "production",
                    "AWS_REGION": self.region,
                    "HITL_TRANSPORT": "sns",
                    "HITL_SNS_TOPIC_ARN": hitl_topic.topic_arn,
                    "METRICS_BACKEND": "cloudwatch",
                    "CLOUDWATCH_NAMESPACE": "AgentPOC",
                    "XRAY_ENABLED": "true",
                    "REFLECTION_ENABLED": "true",
                    "SERVICE_NAME": "enterprise-agent",
                },
                secrets={
                    "JWT_SECRET": ecs.Secret.from_secrets_manager(
                        secretsmanager.Secret.from_secret_name_v2(
                            self, "JWTSecretRef", "/agent/jwt-secret"
                        ),
                        field="key",
                    ),
                    "DATABASE_URL": ecs.Secret.from_secrets_manager(db_secret),
                },
            ),
            public_load_balancer=True,
            assign_public_ip=False,
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        # Health check configuration
        self.service.target_group.configure_health_check(
            path="/health",
            healthy_http_codes="200",
            interval=cdk.Duration.seconds(30),
            timeout=cdk.Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3,
        )

        # -------------------------------------------------------
        # Auto-scaling
        # -------------------------------------------------------
        scaling = self.service.service.auto_scale_task_count(
            min_capacity=2,
            max_capacity=10,
        )

        scaling.scale_on_cpu_utilization(
            "CPUScaling",
            target_utilization_percent=70,
            scale_in_cooldown=cdk.Duration.seconds(60),
            scale_out_cooldown=cdk.Duration.seconds(30),
        )

        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
        )

        # -------------------------------------------------------
        # Outputs
        # -------------------------------------------------------
        cdk.CfnOutput(self, "ServiceURL", value=f"http://{self.service.load_balancer.load_balancer_dns_name}")
        cdk.CfnOutput(self, "ECRRepository", value=self.ecr_repo.repository_uri)
        cdk.CfnOutput(self, "HITLTopicArn", value=hitl_topic.topic_arn)
        cdk.CfnOutput(self, "LogGroupName", value=log_group.log_group_name)
        cdk.CfnOutput(self, "DecisionLogGroupName", value=decision_log_group.log_group_name)
