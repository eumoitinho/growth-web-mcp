import socket
import threading
import time

import pytest
import uvicorn
from mcp.server.fastmcp import FastMCP
from growth_qa.services import check_service


@pytest.fixture(scope='module')
def mcp_url():
    mcp = FastMCP('local-contract-fixture',stateless_http=True,json_response=True)
    @mcp.tool()
    def probe(value: int) -> dict:
        return {'value':value}
    @mcp.tool()
    def broken() -> dict:
        raise ValueError('synthetic failure')
    sock = socket.socket()
    sock.bind(('127.0.0.1',0))
    server = uvicorn.Server(uvicorn.Config(mcp.streamable_http_app(),log_level='critical'))
    thread = threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
    thread.start()
    deadline=time.monotonic()+10
    while not server.started and time.monotonic()<deadline:time.sleep(.02)
    assert server.started
    try:yield f'http://127.0.0.1:{sock.getsockname()[1]}/mcp'
    finally:
        server.should_exit=True
        thread.join(10)
        sock.close()


@pytest.mark.parametrize('variant,expected', [('valid','PASS'),('missing_tool','FAIL'),('forbidden','FAIL'),('upstream_error','FAIL'),('invalid_args','FAIL'),('unauthenticated','FAIL')])
async def test_contract_checker_over_real_mcp(mcp_url,variant,expected):
    cfg={'name':'fixture','url':mcp_url,'required_tools':['probe'],'calls':[{'tool':'probe','read_only':True,'arguments':{'value':3},'schema':{'type':'object','required':['value']}}]}
    if variant=='missing_tool':cfg['required_tools']=['missing']
    if variant=='forbidden':cfg['forbidden_tools']=['probe']
    if variant=='upstream_error':cfg['calls'][0]['tool']='broken'
    if variant=='invalid_args':cfg['calls'][0]['arguments']={}
    if variant=='unauthenticated':cfg['require_unauthenticated_denial']=True
    assert (await check_service(cfg))['status']==expected
