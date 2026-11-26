"""Run against the packaged static site with Playwright and Chromium."""

import argparse
import json
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


def verify_mock_intake(browser):
    page = browser.new_page()
    shared = (FIXTURES / "observations-shared.json").read_text()
    page.evaluate("""window.invocations = [];
      window.google = {script: {run: {
        withSuccessHandler(callback) { this.success = callback; return this; },
        withFailureHandler(callback) { this.failure = callback; return this; },
        submitObservation(...args) {
          window.invocations.push(args);
          if (window.invocations.length === 1) setTimeout(this.failure);
          else setTimeout(() => this.success({status:'duplicate', id:JSON.parse(args[0]).observations[0].id}));
        }
      }}};
    """)
    page.set_content((FIXTURES.parents[1] / "collection" / "Intake.html").read_text())
    page.get_by_label("Contribution JSON").fill(shared)
    page.get_by_label("Pilot invite code").fill("f" * 48)
    submit = page.get_by_role("button", name="Submit observation")
    submit.click()
    assert page.evaluate("window.invocations.length") == 0
    page.get_by_role("checkbox").check()
    submit.click()
    expect(page.get_by_role("status")).to_contain_text("Delivery is unconfirmed")
    expect(page.get_by_label("Contribution JSON")).to_have_value(shared)
    submit.click()
    expect(page.get_by_role("status")).to_contain_text("Already received")
    assert page.evaluate("JSON.stringify(invocations[0]) === JSON.stringify(invocations[1])")
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
        verify_mock_intake(browser)
        print("Hosted intake HTML passed with mocked Google RPC")


if __name__ == "__main__":
    main()
