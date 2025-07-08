import os
import argparse
import json # Import json é necessário
from utils import *

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--spn-auth", action="store_true", default=True)
parser.add_argument("--environment", default="dev")
parser.add_argument("--config-file", default="./config.json")
parser.add_argument("--capacity", default=None, help="Capacity name")
parser.add_argument("--workspace", default=None, help="Workspace name")
parser.add_argument("--admin-upns", default=None, help="Comma-separated list of admin UPNs")

args = parser.parse_args()

# Deployment parameters:
spn_auth = args.spn_auth
environment = args.environment

config = read_pbip_jsonfile(args.config_file)
configEnv = config[args.environment]

# Use command-line arguments if provided, otherwise fallback to config values
capacity_name = args.capacity or configEnv.get("capacity")
workspace_name = args.workspace or configEnv["workspace"]
admin_upns = (args.admin_upns.split(",") if args.admin_upns else []) or configEnv.get("adminUPNs", "").split(",")

# --- MODIFICAÇÃO 1: Lendo os caminhos dinâmicos do config.json ---
semantic_model_path = configEnv["semanticModelPath"]
report_paths = configEnv.get("reportPaths", [])

# --- MODIFICAÇÃO 2: Lógica dinâmica para lidar com parâmetros flexíveis ---
semanticmodel_parameters = configEnv.get("semanticModelsParameters", [])

# Constrói dinamicamente o dicionário de find_and_replace
find_and_replace_dict = {}
for param in semanticmodel_parameters:
    param_name = param["name"]
    param_value = param["value"]
    
    dict_key = (
        r"expressions.tmdl",
        rf'(expression\s+{param_name}\s*=\s*)".*?"'
    )
    dict_value = rf'\1"{param_value}"'
    find_and_replace_dict[dict_key] = dict_value

# Authentication
if spn_auth:
    fab_authenticate_spn()

# Ensure workspace exists
workspace_id = create_workspace(workspace_name=workspace_name, capacity_name=capacity_name, upns=admin_upns)

# Deploy semantic model
# --- MODIFICAÇÃO 3: Usando as variáveis dinâmicas ---
print(f"Deploying Semantic Model from: {semantic_model_path}")
semanticmodel_id = deploy_item(
    semantic_model_path,
    workspace_name=workspace_name,
    find_and_replace=find_and_replace_dict,
)

# Deploy reports
# --- MODIFICAÇÃO 4: Loop dinâmico para os relatórios ---
for report_path in report_paths:
    print(f"Deploying report from: {report_path}")
    deploy_item(
        report_path,
        workspace_name=workspace_name,
        find_and_replace={
            ("definition.pbir", r"\{[\s\S]*\}"): json.dumps(
                {
                    "version": "4.0",
                    "datasetReference": {
                        "byConnection": {
                            "connectionString": None,
                            "pbiServiceModelId": None,
                            "pbiModelVirtualServerName": "sobe_wowvirtualserver",
                            "pbiModelDatabaseName": semanticmodel_id,
                            "name": "EntityDataSource",
                            "connectionType": "pbiServiceXmlaStyleLive",
                        }
                    },
                }
            )
        },
    )

run_fab_command("auth logout")