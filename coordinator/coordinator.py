import asyncio, hashlib, logging, os, time, uuid
from datetime import datetime
from typing import Dict, List
from aiohttp import web

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
log = logging.getLogger("divinemesh.coordinator")

nodes: Dict[str, dict] = {}
proofs: List[dict] = []
tasks: List[dict] = []
stats = {"total_nodes_ever":0,"total_proofs":0,"total_compute_seconds":0,
    "started_at":datetime.utcnow().isoformat()}

def now_ts(): return time.time()
def active_nodes(): return [n for n in nodes.values() if n["last_seen"]>now_ts()-90]
def node_summary(n):
    return {"node_id":n["node_id"],"wallet_address":n["wallet_address"],
        "tier":n["tier"],"score":n["score"],"online":(now_ts()-n["last_seen"])<90,
        "joined_at":n["joined_at"],"last_seen":n["last_seen"],
        "earnings_dmc":n.get("earnings_dmc",0.0)}

@web.middleware
async def cors_middleware(request, handler):
    if request.method=="OPTIONS":
        return web.Response(headers={"Access-Control-Allow-Origin":"*",
            "Access-Control-Allow-Methods":"GET,POST,OPTIONS",
            "Access-Control-Allow-Headers":"Content-Type,Authorization"})
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"]="*"
    return resp

routes = web.RouteTableDef()

@routes.get("/")
async def root(req):
    return web.json_response({"service":"DivineMesh Coordinator",
        "version":"1.0.0","nodes_online":len(active_nodes()),
        "status":"operational","verse":"Matthew 18:20"})

@routes.get("/health")
async def health(req):
    return web.json_response({"status":"ok","ts":now_ts()})

async def do_register(req):
    try: data=await req.json()
    except: raise web.HTTPBadRequest(reason="Invalid JSON")
    node_id=data.get("node_id","").strip()
    wallet=data.get("wallet_address","").strip()
    hw=data.get("hardware",{})
    if not node_id or not node_id.startswith("DM-"):
        raise web.HTTPBadRequest(reason="Invalid node_id")
    if not wallet or not wallet.startswith("0x"):
        raise web.HTTPBadRequest(reason="Invalid wallet_address")
    is_new=node_id not in nodes
    nodes[node_id]={"node_id":node_id,"wallet_address":wallet,"hw":hw,
        "tier":data.get("tier","free"),"score":hw.get("compute_score",1.0),
        "joined_at":nodes.get(node_id,{}).get("joined_at",now_ts()),
        "last_seen":now_ts(),"earnings_dmc":nodes.get(node_id,{}).get("earnings_dmc",0.0)}
    if is_new:
        stats["total_nodes_ever"]+=1
        log.info(f"New node: {node_id}")
    return web.json_response({"status":"registered","node_id":node_id,
        "network":"polygon","heartbeat_interval":30,
        "message":"Welcome! Give and it will be given. Luke 6:38"})

@routes.post("/api/v1/register")
async def register1(req): return await do_register(req)

@routes.post("/api/v1/nodes/register")
async def register2(req): return await do_register(req)

async def do_heartbeat(req):
    try: data=await req.json()
    except: raise web.HTTPBadRequest(reason="Invalid JSON")
    node_id=data.get("node_id","").strip()
    if not node_id or node_id not in nodes:
        raise web.HTTPUnauthorized(reason="Unknown node")
    nodes[node_id]["last_seen"]=now_ts()
    nodes[node_id]["hw"]=data.get("hardware",nodes[node_id]["hw"])
    log.info(f"Heartbeat: {node_id}")
    return web.json_response({"status":"ok","ts":now_ts(),
        "nodes_online":len(active_nodes()),"task":None})

@routes.post("/api/v1/heartbeat")
async def heartbeat1(req): return await do_heartbeat(req)

@routes.post("/api/v1/nodes/heartbeat")
async def heartbeat2(req): return await do_heartbeat(req)

@routes.get("/api/v1/tasks/next")
async def next_task(req):
    node_id=req.rel_url.query.get("node_id","").strip()
    if node_id and node_id in nodes:
        nodes[node_id]["last_seen"]=now_ts()
    pending=[t for t in tasks if t["status"]=="pending"]
    if pending:
        t=pending[0]; t["status"]="assigned"
        t["assigned_to"]=node_id; t["assigned_at"]=now_ts()
        return web.json_response({"task":t})
    return web.json_response({"task":None})

@routes.post("/api/v1/proof")
async def submit_proof(req):
    try: data=await req.json()
    except: raise web.HTTPBadRequest(reason="Invalid JSON")
    node_id=data.get("node_id","").strip()
    if not node_id or node_id not in nodes:
        raise web.HTTPUnauthorized(reason="Unknown node")
    dmc=float(data.get("cpu_seconds",0))*0.001+float(data.get("gpu_seconds",0))*0.004
    proof={"proof_id":str(uuid.uuid4()),"node_id":node_id,"dmc_reward":round(dmc,6),
        "submitted_at":now_ts(),"status":"verified"}
    proofs.append(proof)
    nodes[node_id]["earnings_dmc"]=round(nodes[node_id].get("earnings_dmc",0)+dmc,6)
    stats["total_proofs"]+=1
    log.info(f"Proof: {node_id} +{dmc:.4f} DMC")
    return web.json_response({"status":"verified","proof_id":proof["proof_id"],"dmc_reward":dmc})

@routes.get("/api/v1/stats")
async def get_stats(req):
    return web.json_response({"nodes_online":len(active_nodes()),
        "nodes_total_ever":stats["total_nodes_ever"],
        "total_proofs":stats["total_proofs"],
        "dmc_distributed":round(sum(p["dmc_reward"] for p in proofs),4),
        "verse":"Give, and it will be given to you. Luke 6:38"})

@routes.get("/api/v1/nodes")
async def get_nodes(req):
    nl=sorted(nodes.values(),key=lambda n:n["last_seen"],reverse=True)
    return web.json_response({"nodes":[node_summary(n) for n in nl],"total":len(nl)})

@routes.get("/api/v1/leaderboard")
async def leaderboard(req):
    sl=sorted(nodes.values(),key=lambda n:n.get("earnings_dmc",0),reverse=True)[:20]
    return web.json_response({"leaderboard":[{"rank":i+1,"node_id":n["node_id"],
        "earnings_dmc":n.get("earnings_dmc",0),"online":(now_ts()-n["last_seen"])<90}
        for i,n in enumerate(sl)]})

async def on_startup(app):
    log.info("="*55)
    log.info("  DivineMesh Coordinator v1.0.0")
    log.info('  "For where two or three gather in my name,')
    log.info('   there am I with them." - Matthew 18:20')
    log.info("="*55)

def create_app():
    app=web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    return app

if __name__=="__main__":
    port=int(os.getenv("PORT",8888))
    web.run_app(create_app(),host="0.0.0.0",port=port)
