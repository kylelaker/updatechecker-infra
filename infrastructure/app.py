#!/usr/bin/env python3
import os

from aws_cdk import core as cdk
from stacks.chaliceapp import ChaliceApp

app = cdk.App()
env = cdk.Environment(
    account=os.environ["CDK_DEFAULT_ACCOUNT"],
    region=os.environ["CDK_DEFAULT_REGION"]
)
ChaliceApp(app, "updatecheckerv2", env=env)

app.synth()
