import os
import argparse
import json # Import json é necessário para a substituição nos relatórios
from utils import *

parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--config-file", default="./config-isv.json")
parser.add_argument("--tenant", default=None)

args = parser.parse_args()

current_file = __file__
current_folder = os.path.dirname(current_file)
src_folder = os.path.join(current_folder, "..", "src")

config = read_pbip_jsonfile(args.config_file)
config_environments = config.items()
tenant_arg = args.tenant

for key, value in config_environments:
    
    if (tenant_arg is not None and key.casefold() != tenant_arg.casefold()):
        continue

    print(f"Deploying to tenant: {key}")

    # --- MODIFICAÇÃO 1: Lendo os caminhos dinâmicos do config.json ---
    semantic_model_path = value["semanticModelPath"]
    report_paths = value.get("reportPaths", [])

    capacity_name = value.get("capacity", "none")
    workspace_name = value["workspace"]
    admin_upns = value.get("adminUPNs", "").split(",")
    
    # --- MODIFICAÇÃO 2: Lógica dinâmica para lidar com parâmetros flexíveis ---
    # Este bloco corrige o erro 'AttributeError'
    semanticmodel_parameters = value.get("semanticModelsParameters", [])

    # Constrói dinamicamente o dicionário de find_and_replace para o modelo semântico
    find_and_replace_dict = {}
    for param in semanticmodel_parameters:
        param_name = param["name"]
        param_value = param["value"]
        
        dict_key = (
            r"expressions.tmdl",  # Aplica a regra apenas no arquivo expressions.tmdl
            rf'(expression\s+{param_name}\s*=\s*)".*?"' # Regex dinâmico com o nome do parâmetro
        )
        dict_value = rf'\1"{param_value}"'
        find_and_replace_dict[dict_key] = dict_value

    # Get SPN details from the environment variable and authenticate with the SPN details
    spn_secret_envname = value["spnSecret"]
    spn_secret_raw = os.getenv(spn_secret_envname)

    if (spn_secret_raw is None):
        raise Exception(f"Environment variable '{spn_secret_envname}' not found.")

    spn_client_id, spn_client_secret, spn_tenant_id = spn_secret_raw.split('|', 2)    

    os.environ["FABRIC_CLIENT_ID"] = spn_client_id
    os.environ["FABRIC_CLIENT_SECRET"] = spn_client_secret
    os.environ["FABRIC_TENANT_ID"] = spn_tenant_id

    fab_authenticate_spn()

    # ensure workspace
    create_workspace(
        workspace_name=workspace_name, capacity_name=capacity_name, upns=admin_upns
    )

    # Deploy semantic model
    # --- MODIFICAÇÃO 3: Usando as variáveis dinâmicas ---
    print(f"Deploying Semantic Model from: {semantic_model_path}")
    semanticmodel_id = deploy_item(
        semantic_model_path, # Usa o caminho dinâmico do modelo
        workspace_name=workspace_name,
        find_and_replace=find_and_replace_dict # Usa o dicionário de parâmetros dinâmico
    )

    # Deploy reports
    # --- MODIFICAÇÃO 4: Loop dinâmico para os relatórios ---
    for report_path in report_paths: # Usa a lista de caminhos de relatórios do JSON
        print(f"Deploying report from: {report_path}")
        deploy_item(
            report_path,
            workspace_name=workspace_name,
            find_and_replace={
                # Esta regra complexa atualiza a conexão do relatório para o modelo semântico que acabamos de implantar
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