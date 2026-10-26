#!/usr/bin/env python3
"""Rebuild backend/gateway using the running deployment's Compose project and files."""
import argparse,json,os,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def compose_command(labels,root=ROOT,env_file=None):
    prefix='com.docker.compose.project.'
    project=labels.get('com.docker.compose.project')
    files=labels.get(prefix+'config_files','').split(',')
    if not project or not files or any(not f for f in files):
        raise ValueError('Container has no original Compose project/config_files labels.')
    paths=[Path(f).resolve() for f in files]
    if (root/'compose.yaml').resolve() not in paths:
        raise ValueError('Running backend belongs to another checkout. Run from its project directory.')
    if any(not p.is_file() for p in paths):raise ValueError('An original Compose configuration file is missing.')
    cmd=['docker','compose','--project-name',project]
    recorded=labels.get(prefix+'environment_file','')
    envs=[str(env_file)] if env_file else [v for v in recorded.split(',') if v]
    if not envs and any('selectel' in p.parts for p in paths):
        raise ValueError('Pass --env-file .env.selectel for this Selectel deployment.')
    for value in envs:
        p=Path(value);p=p if p.is_absolute() else root/p
        if not p.is_file():raise ValueError('Original environment file is missing.')
        cmd+=['--env-file',str(p.resolve())]
    for p in paths:cmd+=['-f',str(p)]
    return cmd

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project');p.add_argument('--env-file',type=Path);p.add_argument('--dry-run',action='store_true');a=p.parse_args()
    ids=subprocess.check_output(['docker','ps','--filter','label=com.docker.compose.service=backend','--format','{{.ID}}'],text=True).split()
    matches=[]
    for identifier in ids:
        labels=json.loads(subprocess.check_output(['docker','inspect','--format','{{json .Config.Labels}}',identifier],text=True))
        if a.project and labels.get('com.docker.compose.project')!=a.project:continue
        files=labels.get('com.docker.compose.project.config_files','').split(',')
        if str((ROOT/'compose.yaml').resolve()) in files:matches.append(labels)
    if len(matches)!=1:raise ValueError('Expected one running backend from this checkout. Use --project NAME if several deployments exist.')
    labels=matches[0];cmd=compose_command(labels,env_file=a.env_file)
    print('Updating existing project:',labels['com.docker.compose.project'],flush=True)
    print('Compose files:',labels['com.docker.compose.project.config_files'],flush=True)
    # Existing environment files stay authoritative over accidental shell overrides.
    env=dict(os.environ)
    env_paths=[Path(v) for v in labels.get('com.docker.compose.project.environment_file','').split(',') if v]
    env_paths+=[a.env_file] if a.env_file else [ROOT/'.env']
    for path in env_paths:
        if not path.is_absolute():path=ROOT/path
        if path.is_file():
            for line in path.read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):env.pop(line.split('=',1)[0].strip(),None)
    for key in ['COMPOSE_FILE','COMPOSE_PROJECT_NAME','COMPOSE_PROFILES']:env.pop(key,None)
    commands=[cmd+['config','--quiet'],cmd+['build','backend','gateway'],cmd+['up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','180','backend','gateway'],cmd+['ps','backend','gateway']]
    if a.dry_run:
        print('Dry run: validate configuration, build backend/gateway, recreate only these two services, wait for health. No services changed.')
        return
    for command in commands:subprocess.run(command,cwd=ROOT,env=env,check=True)
    print('Backend and gateway updated. Existing volumes and installation credentials preserved.')

if __name__=='__main__':
    try:main()
    except (ValueError,subprocess.CalledProcessError) as error:raise SystemExit('Update stopped: '+str(error))
