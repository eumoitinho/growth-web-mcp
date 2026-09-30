"""Read-only deployed MCP contract checks. No success for unconfigured services."""
import argparse
import asyncio
import json
import os
from pathlib import Path

import httpx
import jsonschema
import yaml
from mcp import ClientSession
from scripts.smoke_test import connect


def expand(value):
    if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
        name = value[2:-1]
        if not os.environ.get(name):
            raise ValueError(f'Missing environment variable: {name}')
        return os.environ[name]
    if isinstance(value, dict):
        return {k: expand(v) for k, v in value.items()}
    if isinstance(value, list):
        return [expand(v) for v in value]
    return value


def assert_result(result, schema=None):
    if result.isError:
        raise AssertionError('MCP tool returned isError=true')
    if schema is not None:
        data = getattr(result, 'structuredContent', None)
        if data is None:
            parts = [p.text for p in result.content if getattr(p, 'type', None) == 'text']
            if len(parts) != 1:
                raise AssertionError('Expected one JSON content block or structuredContent')
            data = json.loads(parts[0])
        jsonschema.validate(data, schema)


async def check_service(config):
    name = config['name']
    try:
        cfg = expand(config)
    except ValueError:
        return {'service': name, 'status': 'BLOCKED', 'reason': 'Missing environment configuration'}
    try:
        async with asyncio.timeout(cfg.get('timeout_seconds', 60)):
            if cfg.get('require_unauthenticated_denial', False):
                async with httpx.AsyncClient(timeout=15) as http:
                    response = await http.post(cfg['url'], json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}})
                    if response.status_code not in (401, 403):
                        raise AssertionError('Unauthenticated request was not denied')
            async with connect(cfg['url'], cfg.get('headers', {})) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    names = set()
                    cursor = None
                    seen = set()
                    while True:
                        page = await session.list_tools(cursor=cursor)
                        for tool in page.tools:
                            jsonschema.Draft202012Validator.check_schema(tool.inputSchema)
                            if tool.name in names:
                                raise AssertionError('Duplicate tool name')
                            names.add(tool.name)
                        cursor = page.nextCursor
                        if not cursor:
                            break
                        if cursor in seen:
                            raise AssertionError('Repeated tool cursor')
                        seen.add(cursor)
                    if not set(cfg['required_tools']).issubset(names):
                        raise AssertionError('Required tools missing')
                    if set(cfg.get('forbidden_tools', [])) & names:
                        raise AssertionError('Forbidden write tool exposed')
                    for call in cfg.get('calls', []):
                        if not call.get('read_only'):
                            raise ValueError('Contract calls must explicitly declare read_only=true')
                        if call['tool'] not in names:
                            raise AssertionError('Probe tool missing')
                        result = await session.call_tool(call['tool'], call.get('arguments', {}))
                        assert_result(result, call.get('schema'))
        return {'service': name, 'status': 'PASS', 'tools': len(names), 'calls': len(cfg.get('calls', []))}
    except Exception as exc:
        # Do not copy upstream error text: it may contain credentials or customer records.
        return {'service': name, 'status': 'FAIL', 'reason': type(exc).__name__}


async def run(config):
    return [await check_service(service) for service in config['services']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', default='artifacts/services.json')
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    results = asyncio.run(run(config))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2) + '\n')
    for row in results:
        print(f"{row['service']}: {row['status']}")
    raise SystemExit(0 if results and all(row['status'] == 'PASS' for row in results) else 1)


if __name__ == '__main__':
    main()
