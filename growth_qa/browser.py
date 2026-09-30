"""Run configured browser journeys only against explicitly allowed test origins."""
import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qsl
from uuid import uuid4

import yaml
from playwright.async_api import async_playwright
from growth_qa.collect import safe_fields, utc_now
from growth_qa.reconcile import validate
from growth_qa.services import expand


def origin(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Invalid test URL')
    return f'{parsed.scheme}://{parsed.netloc}'


def validate_target(settings, allow_submissions):
    if not allow_submissions or settings.get('environment') != 'test':
        raise ValueError('Browser runs require a test environment and explicit --allow-submissions')
    base = origin(settings['base_url'])
    allowed = {origin(u) for u in settings['allowed_origins']}
    if base not in allowed:
        raise ValueError('Base origin is not allowlisted')
    return allowed


async def run_browser(suite, journey_id, settings, allow_submissions=False, output=None):
    validate(suite, 'journeys')
    allowed = validate_target(settings, allow_submissions)
    journey = next(j for j in suite['journeys'] if j['id'] == journey_id)
    run_id = str(uuid4())
    raw_browser = json.loads(json.dumps(journey['browser']).replace('${RUN_ID}', run_id))
    browser_config = expand(raw_browser)
    evidence = {'version':1, 'run_id':run_id, 'journey_id':journey_id, 'started_at':utc_now(), 'sources':{}, 'observations':[]}
    url = urljoin(settings['base_url'], browser_config['path'])
    if origin(url) not in allowed:
        raise ValueError('Journey URL outside test allowlist')
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query)) | browser_config.get('query', {}) | {'test_run_id':run_id}
    url = parsed._replace(query=urlencode(query)).geturl()
    observations = evidence['observations']
    def record(source, event, fields):
        observations.append({'run_id':run_id, 'source':source, 'event':str(event), 'record_id':str(uuid4()), 'occurred_at':utc_now(), 'fields':safe_fields(fields)})
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(service_workers='block', **settings.get('context', {}))
        if settings.get('trace', False):
            await context.tracing.start(screenshots=True, snapshots=True, sources=False)
        async def binding(source, data):
            if isinstance(data, dict) and isinstance(data.get('event'), str):
                record('browser', data['event'], data)
        await context.expose_binding('__growthEvidence', binding)
        # Observe, never fabricate events or inject correlation into application payloads.
        await context.add_init_script('''(() => {
          let layer = [];
          const wrap = (value) => {
            if (!Array.isArray(value) || value.__qaWrapped) return value;
            const original = value.push;
            Object.defineProperty(value, '__qaWrapped', {value:true});
            value.push = function(...items) {
              for (const item of items) {
                let event = item;
                if (item && item[0] === 'event') event = { ...item[2], event:item[1] };
                if (event && typeof event.event === 'string') window.__growthEvidence(event);
              }
              return original.apply(this, items);
            };
            return value;
          };
          Object.defineProperty(window, 'dataLayer', { configurable:true, get:()=>layer, set:(v)=>{layer=wrap(v);} });
          layer = wrap(layer);
        })();''')
        async def route(request_route):
            request = request_route.request
            permitted = allowed | {origin(u) for u in settings.get('allowed_request_origins', [])}
            if request.url.startswith(('http://','https://')) and origin(request.url) not in permitted:
                await request_route.abort()
            else:
                await request_route.continue_()
        await context.route('**/*', route)
        def inspect(request):
            for rule in settings.get('network_rules', []):
                parsed_request = urlparse(request.url)
                if origin(request.url) != origin(rule['origin']) or parsed_request.path != rule['path']:
                    continue
                data = dict(parse_qsl(parsed_request.query))
                raw = request.post_data or ''
                # GA4 query/form payloads; newline-delimited batches produce one observation per event.
                for line in raw.splitlines() or ['']:
                    fields = data | dict(parse_qsl(line))
                    event = fields.get('en')
                    if event:
                        record('network', event, {k.removeprefix('ep.'):v for k,v in fields.items() if k.startswith('ep.')})
        context.on('request', inspect)
        page = await context.new_page()
        page.set_default_timeout(settings.get('timeout_ms', 15000))
        try:
            await page.goto(url, referer=browser_config.get('referrer'), wait_until='domcontentloaded')
            for step in browser_config['steps']:
                locator = page.locator(step['selector'])
                if step['action'] == 'fill': await locator.fill(step['value'].replace('${RUN_ID}',run_id))
                elif step['action'] == 'click': await locator.click()
                elif step['action'] == 'check': await locator.check()
                elif step['action'] == 'wait_visible': await locator.wait_for(state='visible')
            await page.wait_for_timeout(browser_config.get('settle_ms', 500))
            for source in ('browser','network'):
                evidence['sources'][source] = {'status':'complete', 'checked_at':utc_now()}
        except Exception as exc:
            for source in ('browser','network'):
                evidence['sources'][source] = {'status':'error', 'checked_at':utc_now(), 'error_code':type(exc).__name__}
        finally:
            if settings.get('trace', False) and output:
                trace = Path(output).with_suffix('.trace.zip')
                trace.parent.mkdir(parents=True, exist_ok=True)
                await context.tracing.stop(path=str(trace))
            await context.close()
            await browser.close()
    validate(evidence, 'evidence')
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(evidence,indent=2)+'\n')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',required=True)
    parser.add_argument('--journey',required=True)
    parser.add_argument('--settings',required=True)
    parser.add_argument('--out',default='artifacts/evidence.json')
    parser.add_argument('--allow-submissions',action='store_true')
    args = parser.parse_args()
    evidence = asyncio.run(run_browser(yaml.safe_load(Path(args.suite).read_text()),args.journey,yaml.safe_load(Path(args.settings).read_text()),args.allow_submissions,args.out))
    print(f"Run {evidence['run_id']}: {args.out}")
    raise SystemExit(1 if any(s['status']=='error' for s in evidence['sources'].values()) else 0)


if __name__ == '__main__':
    main()
