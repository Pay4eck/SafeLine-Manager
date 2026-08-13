from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from urllib.parse import quote

import json5
from jinja2 import BaseLoader, Environment, TemplateNotFound


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_INSTALL_PREFIX = "opt/hiddify-manager/"
XRAY_CONFIG_SOURCE = REPOSITORY_ROOT / "xray" / "configs"


class RepositoryTemplateLoader(BaseLoader):
    """Map Hiddify's absolute install-time includes onto this checkout."""

    def get_source(self, environment: Environment, template: str):
        normalized_name = template.replace("\\", "/").lstrip("/")
        if normalized_name.startswith(UPSTREAM_INSTALL_PREFIX):
            normalized_name = normalized_name[len(UPSTREAM_INSTALL_PREFIX):]

        candidate = (REPOSITORY_ROOT / normalized_name).resolve()
        try:
            candidate.relative_to(REPOSITORY_ROOT)
        except ValueError as error:
            raise TemplateNotFound(template) from error
        if not candidate.is_file():
            raise TemplateNotFound(template)

        source = candidate.read_text(encoding="utf-8-sig")
        original_stat = candidate.stat()

        def is_up_to_date() -> bool:
            try:
                current_stat = candidate.stat()
            except OSError:
                return False
            return (
                current_stat.st_mtime_ns == original_stat.st_mtime_ns
                and current_stat.st_size == original_stat.st_size
            )

        return source, str(candidate), is_up_to_date


def load_hiddify_context(path: Path) -> dict:
    """Apply the same current.json normalization as common/jinja.py."""

    configs = json.loads(path.read_text(encoding="utf-8"))
    configs["chconfigs"] = {
        int(child_id): child_config
        for child_id, child_config in configs["chconfigs"].items()
    }
    configs["hconfigs"] = configs["chconfigs"][0]
    return configs


def render_xray_config_directory(
    context_path: Path,
    runtime_path: Path,
    output_directory: Path,
) -> list[Path]:
    """Render every Xray JSON template using Hiddify's production pipeline."""

    configs = load_hiddify_context(context_path)
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    command_outputs = runtime["command_outputs"]

    def controlled_exec(command: str) -> str:
        if command not in command_outputs:
            raise RuntimeError(
                "Template requested an undocumented host command: " + repr(command)
            )
        return command_outputs[command]

    environment = Environment(
        loader=RepositoryTemplateLoader(),
        autoescape=False,
        keep_trailing_newline=True,
    )
    environment.globals["enumerate"] = enumerate
    environment.filters["b64encode"] = lambda value: base64.b64encode(
        value.encode("utf-8") if isinstance(value, str) else value
    ).decode("utf-8")
    environment.filters["quote"] = lambda value: quote(value, safe="")
    environment.filters["hexencode"] = lambda value: "".join(
        hex(ord(character))[2:].zfill(2) for character in value
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    rendered_paths: list[Path] = []
    for template_path in sorted(XRAY_CONFIG_SOURCE.rglob("*.json.j2")):
        template_name = template_path.relative_to(REPOSITORY_ROOT).as_posix()
        template = environment.get_template(template_name)
        rendered = template.render(**configs, exec=controlled_exec, os=os)

        # This is the same JSON5-to-JSON normalization used by common/jinja.py.
        parsed = json5.loads(rendered)
        normalized = json5.dumps(
            parsed,
            trailing_commas=False,
            indent=2,
            quote_keys=True,
        )
        relative_output = template_path.relative_to(XRAY_CONFIG_SOURCE)
        output_path = output_directory / relative_output.with_suffix("")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(normalized, encoding="utf-8")
        rendered_paths.append(output_path)

    return rendered_paths


def load_rendered_documents(config_directory: Path) -> dict[str, dict]:
    return {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(config_directory.rglob("*.json"))
    }


def validate_rendered_contract(
    config_directory: Path,
    context_path: Path,
    keypair_path: Path,
) -> dict[str, object]:
    """Assert the requested server-config sections before Xray parses them."""

    documents = load_rendered_documents(config_directory)
    context = load_hiddify_context(context_path)
    keypair = json.loads(keypair_path.read_text(encoding="utf-8"))
    hconfigs = context["hconfigs"]

    expected_users = [user["uuid"] for user in context["users"]]
    for user_id in expected_users:
        import uuid

        if str(uuid.UUID(user_id)) != user_id:
            raise AssertionError(f"Invalid canonical user UUID: {user_id}")

    inbounds = [
        inbound
        for document in documents.values()
        for inbound in document.get("inbounds", [])
    ]
    reality_inbounds = [
        inbound
        for inbound in inbounds
        if inbound.get("streamSettings", {}).get("security") == "reality"
    ]
    expected_reality_domains = {
        domain["domain"]: domain
        for domain in context["domains"]
        if domain["mode"].startswith("special_reality_")
    }
    if len(reality_inbounds) != len(expected_reality_domains):
        raise AssertionError("Not every Reality fixture domain rendered an inbound")

    for inbound in reality_inbounds:
        if inbound["protocol"] != "vless":
            raise AssertionError("Reality inbound is not VLESS")
        clients = inbound["settings"]["clients"]
        if [client["id"] for client in clients] != expected_users:
            raise AssertionError("Reality client UUIDs differ from current.json users")

        stream = inbound["tag"].split("_")[1]
        expected_flow = "xtls-rprx-vision" if stream == "tcp" else ""
        if any(client["flow"] != expected_flow for client in clients):
            raise AssertionError(f"Unexpected VLESS flow for Reality {stream}")

        reality = inbound["streamSettings"]["realitySettings"]
        domain = reality["serverNames"][0]
        if domain not in expected_reality_domains:
            raise AssertionError(f"Unexpected Reality serverName: {domain}")
        if reality["serverNames"] != [domain] or reality["dest"] != f"{domain}:443":
            raise AssertionError("Reality SNI/serverNames and destination diverged")
        if reality["privateKey"] != keypair["private_key"]:
            raise AssertionError("Reality private key is not the test-only X25519 key")
        for short_id in reality["shortIds"]:
            if short_id and (
                len(short_id) > 16
                or len(short_id) % 2
                or any(character not in "0123456789abcdefABCDEF" for character in short_id)
            ):
                raise AssertionError(f"Invalid Reality shortId: {short_id}")

    generic_inbounds = [
        inbound for inbound in inbounds if inbound.get("tag", "").startswith("v10-")
    ]
    expected_generic_tags = {
        f"v10-{protocol}-{stream}"
        for protocol in ("vless", "vmess", "trojan")
        for stream in ("xhttp", "ws", "grpc", "tcp", "httpupgrade")
    }
    if {inbound["tag"] for inbound in generic_inbounds} != expected_generic_tags:
        raise AssertionError("The full protocol/transport inbound matrix was not rendered")
    for inbound in generic_inbounds:
        clients = inbound["settings"]["clients"]
        identity_field = "id" if inbound["protocol"] in {"vless", "vmess"} else "password"
        if [client[identity_field] for client in clients] != expected_users:
            raise AssertionError(
                f"{inbound['tag']} client identities differ from current.json users"
            )

    routing = documents["03_routing.json"]["routing"]
    outbounds = documents["06_outbounds.json"]["outbounds"]
    outbound_tags = {outbound["tag"] for outbound in outbounds}
    if outbound_tags != {"freedom", "WARP", "blackhole", "forbidden_sites", "DNS-Internal"}:
        raise AssertionError("Unexpected outbound set")
    referenced_tags = {
        rule["outboundTag"]
        for rule in routing["rules"]
        if "outboundTag" in rule
    }
    if not referenced_tags.issubset(outbound_tags | {"api"}):
        raise AssertionError("Routing refers to an unknown outbound")

    dns = documents["02_dns.json"]["dns"]
    if dns["servers"][0] != hconfigs["dns_server"] or dns["tag"] != "DNS-Internal":
        raise AssertionError("DNS settings differ from current.json")
    log = documents["00_log.json"]["log"]
    if log["loglevel"] != hconfigs["log_level"].lower():
        raise AssertionError("Logging level differs from current.json")

    api = documents["01_api.json"]["api"]
    expected_services = {"HandlerService", "LoggerService", "StatsService"}
    if set(api["services"]) != expected_services or api["tag"] != "api":
        raise AssertionError("Xray API services are incomplete")
    if documents["08_stats.json"].get("stats") != {}:
        raise AssertionError("Xray statistics section is missing")
    policy = documents["04_policy.json"]["policy"]
    if not all(policy["system"].values()):
        raise AssertionError("System traffic statistics policy is incomplete")

    return {
        "files": len(documents),
        "inbounds": len(inbounds),
        "reality_inbounds": len(reality_inbounds),
        "generic_inbounds": len(generic_inbounds),
        "users": len(expected_users),
        "routing_rules": len(routing["rules"]),
        "outbounds": sorted(outbound_tags),
        "dns_servers": dns["servers"],
        "api_services": sorted(expected_services),
        "statistics": True,
        "logging": log["loglevel"],
    }
