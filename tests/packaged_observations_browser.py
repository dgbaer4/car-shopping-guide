"""Run against the packaged static site with Playwright and Chromium."""

import argparse
from html import escape
import hashlib
import hmac
import json
from urllib.parse import parse_qs, urljoin
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def verify_page(browser, site, width, height):
    page = browser.new_page(viewport={"width": width, "height": height}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    profile = json.loads((FIXTURES / "walnut-creek-profile.json").read_text())
    page.add_init_script(f"""if (!localStorage.getItem('csg-v02')) {{
      localStorage.setItem('csg-v02', JSON.stringify({{...{json.dumps(profile)}, page: 'review'}}));
    }}""")
    page.goto(site)
    page.get_by_role("button", name="Shopping Tracker").click()
    panel = page.locator("#shopping-tracker")
    add = panel.get_by_role("button", name="Add Vehicle Observation")
    add.click()
    form = panel.locator("form")
    save = form.get_by_role("button", name="Save observation")
    save.click()
    assert form.evaluate("form => !form.checkValidity()")
    for name, value in [("year", "2024"), ("make", "Sample"), ("model", "Road Runner"), ("price", "24900.99")]:
        form.locator(f"[name={name}]").fill(value)
    form.locator("[name=condition]").select_option("new")
    form.locator("[name=type]").select_option("asking")
    form.locator("[name=scope]").select_option("vehicle")
    form.get_by_text("Optional vehicle details").click()
    form.locator("[name=listingUrl]").fill("https://example.com/vehicle?tracking=test")
    form.locator("[name=nickname]").fill("Fixture")
    form.locator("[name=privateNotes]").fill("Private note\nSecond line")
    save.click()
    expect(panel.get_by_role("status")).to_have_text("Saved locally.")
    card = panel.locator("article").first
    expect(card).to_contain_text("$24,900.99")
    expect(card).to_contain_text("Advertised asking price")
    expect(card.get_by_role("link", name="Original listing")).to_have_attribute(
        "href", "https://example.com/vehicle?tracking=test"
    )
    permalink = card.get_by_role("link", name="Observation permalink").get_attribute("href")
    page.goto(site + permalink)
    page.reload()
    expect(card).to_contain_text("Second line")
    card.get_by_role("button", name="Edit", exact=True).click()
    form.locator("[name=condition]").select_option("used")
    form.locator("[name=type]").select_option("purchase")
    form.locator("[name=scope]").select_option("out_the_door")
    save.click()
    expect(card).to_contain_text("Reported completed purchase")
    expect(card).to_contain_text("including taxes and fees")

    card.get_by_role("button", name="Share or export contribution").click()
    actions = panel.locator(".observation-actions")
    expect(actions).to_be_hidden()
    expect(panel.locator("pre")).not_to_contain_text("Private note")
    expect(panel.locator("pre")).not_to_contain_text("nickname")
    panel.get_by_role("checkbox", name="I agree", exact=False).check()
    expect(actions).to_be_visible()
    panel.get_by_role("checkbox", name="Include ZIP", exact=False).check()
    expect(actions).to_be_hidden()
    expect(panel.locator("pre")).to_contain_text("https://example.com/vehicle")
    expect(panel.locator("pre")).not_to_contain_text("tracking")
    panel.get_by_role("checkbox", name="I agree", exact=False).check()
    with page.expect_download() as fetched:
        actions.get_by_role("button", name="JSON", exact=True).click()
    contribution = json.loads(Path(fetched.value.path()).read_text())["observations"][0]
    assert contribution["nickname"] == "Fixture"
    assert "privateNotes" not in contribution and "interest" not in contribution
    panel.get_by_role("button", name="Back to tracker").click()
    card.get_by_label("Interest").select_option("DON’T THINK SO")
    expect(panel.locator("article")).to_have_count(0)
    panel.get_by_role("button", name="Show DON’T THINK SO (1)").click()
    expect(card).to_be_visible()
    card.get_by_label("Interest").select_option("GOOD")
    expect(panel.get_by_role("heading", name="GOOD", exact=True)).to_be_visible()
    card.get_by_text("Export private copy").click()
    with page.expect_download() as backup:
        card.get_by_role("button", name="Markdown").click()
    page.once("dialog", lambda dialog: dialog.accept())
    card.get_by_role("button", name="Delete", exact=True).click()
    expect(panel.locator("article")).to_have_count(0)
    panel.get_by_text("Export or import observations").click()
    panel.locator("input[type=file]").set_input_files(
        {"name": "backup.md", "mimeType": "text/markdown", "buffer": Path(backup.value.path()).read_bytes()}
    )
    expect(panel.get_by_role("status")).to_contain_text("Restored 1")
    expect(card).to_contain_text("Private note")
    expect(card.get_by_label("Interest")).to_have_value("GOOD")

    panel.get_by_role("button", name="Close tracker").click()
    page.get_by_role("button", name="See recommendations").click()
    results = page.locator("#screen")
    expect(results.get_by_role("heading", name="Vehicle recommendations")).to_be_visible()
    result_card = results.locator("article").first
    result_id = result_card.locator("h3").get_attribute("id")
    result_title = result_card.locator("h3").inner_text()
    expect(results.get_by_role("link", name="Jump to financial assumptions")).to_be_visible()
    for linked in results.locator("ul a[href^='#vehicle-']").all():
        assert page.locator(linked.get_attribute("href")).count() == 1
    result_card.get_by_role("button", name="Add Vehicle Observation").click()
    prefilled_title = " ".join(form.locator(f"[name={name}]").input_value() for name in ("year", "make", "model"))
    assert prefilled_title == result_title
    assert form.locator("[name=condition]").input_value() in {"new", "used"}
    form.locator("[name=price]").fill("21500")
    form.locator("[name=type]").select_option("quote")
    form.locator("[name=scope]").select_option("vehicle")
    save.click()
    panel.get_by_role("link", name="Recommendation and ownership costs").click()
    expect(page.locator("#" + result_id)).to_be_focused()
    result_card.get_by_role("link", name="View related observations").click()
    expect(panel.locator("article")).to_have_count(1)
    expect(panel.locator("article")).to_contain_text(result_title)
    expect(panel.locator("article")).to_contain_text("Dealer or seller quote")
    panel.get_by_role("button", name="Close tracker").click()
    result_card.get_by_role("button", name="Show more financial information").click()
    expect(result_card.get_by_text("Net ownership cost", exact=True)).to_be_visible()
    price = result_card.get_by_label("Vehicle purchase price override")
    price.fill("21500")
    price.press("Tab")
    expect(result_card).to_contain_text("$24,150")
    page.get_by_role("button", name="Compare matches with sourced prices").click()
    expect(results.locator("article").first).to_contain_text("Published market pricing")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors, errors
    page.close()


def verify_mock_intake(browser, site, width, height, blocked_storage=False):
    endpoint = "https://script.google.com/macros/s/fixture/exec"
    fixture = json.loads((FIXTURES / "observations-private.json").read_text())["observations"][0]
    template = (FIXTURES.parents[1] / "collection" / "Intake.html").read_text()
    page = browser.new_page(viewport={"width": width, "height": height})
    requests = []
    page.route("**/engine/observation-config.mjs", lambda route: route.fulfill(
        content_type="text/javascript", body=f"export const intakeUrl = {json.dumps(endpoint)};",
    ))

    def receive_handoff(route):
        request = route.request
        assert request.method == "POST"
        assert request.url == endpoint
        data = parse_qs(request.post_data)
        assert set(data) == {"payload"}
        payload = data["payload"][0]
        observation = json.loads(payload)["observations"][0]
        assert observation["id"] == fixture["id"]
        assert not {"privateNotes", "interest", "listingUrl", "nickname", "zip"} & observation.keys()
        requests.append(observation["id"])
        route.fulfill(content_type="text/html", body=template.replace("<?= payload ?>", escape(payload)))

    page.route(endpoint, receive_handoff)
    page.add_init_script(f"""
      if (location.origin === {json.dumps(urljoin(site, '/').rstrip('/'))}) {{
        const record = {json.dumps(fixture)};
        localStorage.setItem('csg-observation-v1/' + record.id, JSON.stringify(record));
      }}
      if (location.href === {json.dumps(endpoint)}) {{
        if ({json.dumps(blocked_storage)}) {{
          for (const kind of ['localStorage', 'sessionStorage']) {{
            Object.defineProperty(window, kind, {{get() {{throw new DOMException('Mock blocked', 'SecurityError');}}}});
          }}
        }}
        window.invocations = [];
        window.google = {{script: {{run: {{
          withSuccessHandler(callback) {{ this.success = callback; return this; }},
          withFailureHandler(callback) {{ this.failure = callback; return this; }},
          enrollDevice(invite, remember, nonce) {{
            window.invocations.push(['enroll', remember, /^[a-f0-9]{{64}}$/.test(nonce)]);
            const result = invite === 'mock input'
              ? {{status:'enrolled', token:'11111111-1111-4111-8111-111111111111.' + '2'.repeat(64),
                  expiresAt:Date.now()+60000}}
              : {{status:'rejected', message:'Invitation was not accepted.'}};
            setTimeout(() => this.success(result));
          }},
          submitObservation(...args) {{
            window.invocations.push(['submit', ...args]);
            const attempts = window.invocations.filter(row => row[0] === 'submit').length;
            const id = JSON.parse(args[0]).observations[0].id;
            if (attempts === 1) setTimeout(this.failure);
            else setTimeout(() => this.success({{status:'duplicate',
              id: attempts === 2 ? 'foreign id' : id, receivedAt:'2026-11-26T01:00:00.000Z',
              expiresAt:Date.now()+60000}}));
          }}
        }}}}}};
      }}
    """)

    def handoff():
        page.goto(site + "#observation-" + fixture["id"])
        panel = page.locator("#shopping-tracker")
        panel.get_by_role("button", name="Share or export contribution").click()
        proceed = panel.get_by_role("button", name="Continue to Share Price")
        expect(proceed).to_be_hidden()
        panel.get_by_role("checkbox", name="I agree", exact=False).check()
        with page.expect_navigation(url=endpoint):
            proceed.click()

    handoff()
    assert requests == [fixture["id"]]
    page.get_by_label("Pilot invitation").fill("wrong input")
    page.get_by_role("button", name="Enroll device").click()
    expect(page.get_by_role("status")).to_contain_text("Invitation was not accepted")
    page.get_by_label("Pilot invitation").fill("mock input")
    page.get_by_role("checkbox", name="Remember this device").check()
    page.get_by_role("button", name="Enroll device").click()
    expect(page.get_by_role("status")).to_contain_text("Device enrolled")
    if blocked_storage:
        expect(page.get_by_role("status")).to_contain_text("Browser storage is blocked")
    assert page.evaluate("invocations[1][1] && invocations[1][2]")
    send = page.get_by_role("button", name="Share Price", exact=True)
    send.click()
    assert page.evaluate("invocations.length") == 2
    page.get_by_role("checkbox", name="I agree", exact=False).check()
    send.click()
    expect(page.get_by_role("status")).to_contain_text("The response is unconfirmed")
    send.click()
    expect(page.get_by_role("status")).to_contain_text("Delivery is unconfirmed")
    send.click()
    expect(page.get_by_role("status")).to_contain_text("Already received. Observation ID " + fixture["id"])
    assert page.evaluate("JSON.stringify(invocations[2]) === JSON.stringify(invocations[4])")

    handoff()
    assert len(requests) == 2
    assert page.evaluate("invocations.length") == 0
    if blocked_storage:
        expect(page.get_by_label("Pilot invitation")).to_be_visible()
    else:
        expect(page.get_by_label("Pilot invitation")).to_be_hidden()
        page.get_by_role("button", name="Forget this device").click()
        expect(page.get_by_label("Pilot invitation")).to_be_visible()
        assert page.evaluate("localStorage.getItem('csg-pilot-device-v1') === null")
    page.close()


def verify_credential_generator(browser, site):
    page = browser.new_page(viewport={"width": 768, "height": 1024})
    page.goto(site + "owner-credentials.html")
    page.get_by_role("button", name="Generate a key for first setup").click()
    key = page.get_by_label("Token key", exact=True).input_value()
    assert len(bytes.fromhex(key)) == 32
    page.get_by_role("button", name="Generate a seven-day invitation").click()
    expect(page.get_by_role("status")).to_contain_text("Copy the settings value")
    invite = page.get_by_label("Private invitation", exact=False).input_value()
    assert invite[-4:].isdigit() and invite[:-4].isalpha()
    config = json.loads(page.get_by_label("INVITATION value for Apps Script").input_value())
    expected = hmac.new(key.encode(), ("invite:" + invite.lower()).encode(), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(config["digest"], expected)
    assert page.evaluate("localStorage.length === 0 && sessionStorage.length === 0")
    page.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", help="Packaged site URL with trailing slash")
    parser.add_argument("--chromium", help="Use an existing Chromium executable")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=args.chromium, args=["--no-sandbox"])
        for width, height in ((390, 844), (844, 390), (768, 1024), (1024, 768), (1280, 900)):
            verify_page(browser, args.site, width, height)
            print(f"Packaged observation and commuter checks passed at {width} × {height}")
        for width, height in ((390, 844), (768, 1024)):
            verify_mock_intake(browser, args.site, width, height)
            print(f"Direct cross-origin form and hosted receipt mock passed at {width} × {height}")
        verify_mock_intake(browser, args.site, 768, 1024, blocked_storage=True)
        print("Hosted submission with blocked storage passed")
        verify_credential_generator(browser, args.site)
        print("Local owner credential generation and HMAC compatibility passed")


if __name__ == "__main__":
    main()
