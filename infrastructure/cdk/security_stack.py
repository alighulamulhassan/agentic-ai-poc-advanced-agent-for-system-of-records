"""
Security Stack — Cognito User Pool, WAF, Secrets Manager.

Provisions:
  - Cognito User Pool + App Client (authentication)
  - Cognito Identity Pool (federated access to AWS services)
  - WAF Web ACL (rate limiting, managed rule groups)
  - Secrets Manager secrets (DB credentials, JWT secret, API keys)

Session for audience (Month 6 Lab):
  TODO: Add a Cognito Lambda trigger (Pre-Token-Generation) that
  injects the user's role (readonly/agent/supervisor) into the JWT
  so our auth.py RBAC can read it without a DB lookup.
"""
import aws_cdk as cdk
import aws_cdk.aws_cognito as cognito
import aws_cdk.aws_secretsmanager as secretsmanager
import aws_cdk.aws_wafv2 as wafv2
from constructs import Construct


class SecurityStack(cdk.Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # -------------------------------------------------------
        # Cognito User Pool
        # -------------------------------------------------------
        self.user_pool = cognito.UserPool(
            self, "AgentUserPool",
            user_pool_name="enterprise-agent-users",
            self_sign_up_enabled=False,        # invite-only
            sign_in_aliases=cognito.SignInAliases(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            custom_attributes={
                "role": cognito.StringAttribute(mutable=True),
            },
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True),
            advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        self.app_client = self.user_pool.add_client(
            "AgentAppClient",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
            ),
            generate_secret=False,
            access_token_validity=cdk.Duration.hours(1),
            id_token_validity=cdk.Duration.hours(1),
            refresh_token_validity=cdk.Duration.days(30),
        )

        # -------------------------------------------------------
        # Secrets Manager
        # -------------------------------------------------------
        self.jwt_secret = secretsmanager.Secret(
            self, "JWTSecret",
            secret_name="/agent/jwt-secret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"key": "placeholder"}',
                generate_string_key="key",
                password_length=64,
                exclude_punctuation=True,
            ),
        )

        self.api_keys_secret = secretsmanager.Secret(
            self, "APIKeys",
            secret_name="/agent/api-keys",
            description="Comma-separated valid API keys for service-to-service auth",
        )

        # -------------------------------------------------------
        # WAF Web ACL
        # -------------------------------------------------------
        self.waf = wafv2.CfnWebACL(
            self, "AgentWAF",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            scope="REGIONAL",
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="AgentWAF",
                sampled_requests_enabled=True,
            ),
            rules=[
                # AWS Managed Rules — common threats
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="CommonRules",
                        sampled_requests_enabled=True,
                    ),
                ),
                # Rate limiting — 1000 req/5min per IP
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=2,
                    action=wafv2.CfnWebACL.RuleActionProperty(block={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=1000,
                            aggregate_key_type="IP",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimit",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
        )

        # -------------------------------------------------------
        # Outputs
        # -------------------------------------------------------
        cdk.CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        cdk.CfnOutput(self, "AppClientId", value=self.app_client.user_pool_client_id)
        cdk.CfnOutput(self, "JWTSecretArn", value=self.jwt_secret.secret_arn)
