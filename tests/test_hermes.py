import json


def test_core_package_registers_hermes_tools():
    import daedalus

    class Ctx:
        def __init__(self):
            self.tools = {}
            self.hooks = {}

        def register_tool(self, name, toolset, schema, handler):
            self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler}

        def register_hook(self, name, handler):
            self.hooks[name] = handler

    ctx = Ctx()
    daedalus.register(ctx)
    assert "treasury_run_paid_audit" in ctx.tools
    assert ctx.tools["treasury_intake"]["toolset"] == "treasury"
    assert {"on_session_start", "on_session_end"} <= set(ctx.hooks)


def test_hermes_tool_sequence_blocks_without_human_approval(tmp_path, monkeypatch):
    from daedalus import config
    from daedalus import hermes

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "AUDIT_LOG_PATH", tmp_path / "d.log")
    monkeypatch.setattr(config, "ORDER_STORE_PATH", tmp_path / "orders.json")
    monkeypatch.setattr(config, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(config, "STRIPE_ENABLED", False)
    monkeypatch.setattr(config, "DAEDALUS_MEMORY_ENABLED", "false")

    quoted = json.loads(hermes.treasury_intake({"target": "https://example.com", "customer": "judge"}))
    assert quoted["state"] == "quoted"
    collected = json.loads(hermes.treasury_collect({"order": quoted["id"]}))
    assert collected["state"] == "funded"
    fulfilled = json.loads(hermes.treasury_fulfill({"order": quoted["id"]}))
    assert fulfilled["state"] == "funded_unfulfilled"
    assert fulfilled["spend_decision"]["protection"] == "economics"
