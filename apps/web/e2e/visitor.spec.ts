import { expect, test, type Page } from "@playwright/test";

// A 1x1 GIF stands in for the NWS radar loop so the tests never reach the internet.
const PIXEL = Buffer.from("R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==", "base64");

test.beforeEach(async ({ page }) => {
  await page.route("https://radar.weather.gov/**", (route) =>
    route.fulfill({ status: 200, contentType: "image/gif", body: PIXEL }),
  );
});

async function addLocation(page: Page, query: string, place: RegExp, name?: string) {
  await page.getByPlaceholder("Search a city or place").fill(query);
  await page.getByRole("button", { name: place }).first().click();
  if (name) await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Save location" }).click();
}

test("new visitor adds a location, sees a forecast, and keeps it after reload", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Your weather.")).toBeVisible();
  await page.getByRole("button", { name: "Add your first location" }).click();
  await addLocation(page, "Orlando", /Orlando/);

  await expect(page).toHaveURL(/\/weather\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("heading", { name: "Next 24 hours" })).toBeVisible();
  await expect(page.getByRole("list", { name: "Daily forecast" }).getByRole("listitem").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Radar now" })).toBeVisible();
  await expect(page.getByRole("img", { name: /NWS radar KMLB/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How far out can you trust it?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How sure is the rain?" })).toBeVisible();
  await expect(page.getByText("Forecast confidence")).toBeVisible();
  // The URL holds an opaque id, never coordinates.
  expect(page.url()).not.toMatch(/28\.5|81\.3/);

  const cookies = await page.context().cookies();
  const visitor = cookies.find((c) => c.name === "weather_visitor");
  expect(visitor?.httpOnly).toBe(true);
  expect(visitor?.sameSite).toBe("Lax");

  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/\/weather\//);
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible();
});

test("a second visitor cannot open the first visitor's location", async ({ browser }) => {
  const first = await browser.newContext();
  const page = await first.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: "Add your first location" }).click();
  await addLocation(page, "Denver", /Denver/);
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible({ timeout: 20_000 });
  const privateUrl = page.url();

  const second = await browser.newContext();
  const intruder = await second.newPage();
  await intruder.goto(privateUrl);
  await expect(intruder.getByRole("heading", { name: "Location not found" })).toBeVisible();
  await expect(intruder.getByText("Denver")).toHaveCount(0);

  await first.close();
  await second.close();
});

test("visitor can add several locations, switch between them, and view forecast history", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Add your first location" }).click();
  await addLocation(page, "Crescent", /Crescent Beach/);
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible({ timeout: 20_000 });

  // The grid button opens the cities page, where a city can be added.
  await page.getByRole("link", { name: "All cities" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Cities" })).toBeVisible();
  await page.getByRole("button", { name: "Add city" }).click();
  await addLocation(page, "Jackson", /Jackson Hole/, "Jackson Hole");
  await expect(page.getByRole("heading", { level: 1, name: "Jackson Hole" })).toBeVisible({ timeout: 20_000 });

  // The floating pill steps between cities.
  const dock = page.getByRole("navigation", { name: "Cities" });
  await expect(dock).toContainText("2 of 2");
  await dock.getByRole("link", { name: "Previous city: Home" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible();

  // Advanced detail for a day.
  await page.getByRole("list", { name: "Daily forecast" }).getByRole("button").nth(1).click();
  await expect(page.getByRole("dialog")).toContainText("10th percentile");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

  await page.getByRole("link", { name: /How has this forecast changed/ }).click();
  await expect(page.getByRole("heading", { name: "How the forecast changed" })).toBeVisible();
  await expect(page.getByRole("row", { name: /^High/ })).toBeVisible();
});

test("visitor can reorder cities by dragging, and the first city opens at start", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "drags with a mouse");
  await page.goto("/");
  await page.getByRole("button", { name: "Add your first location" }).click();
  await addLocation(page, "Orlando", /Orlando/);
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible({ timeout: 20_000 });
  await page.getByRole("link", { name: "All cities" }).click();
  await page.getByRole("button", { name: "Add city" }).click();
  await addLocation(page, "Denver", /Denver/);
  await expect(page.getByRole("heading", { level: 1, name: "Denver" })).toBeVisible({ timeout: 20_000 });

  await page.getByRole("link", { name: "All cities" }).click();
  const grid = page.getByRole("list", { name: "Your cities" });
  const denver = grid.getByRole("link", { name: /^Denver/ });
  const home = grid.getByRole("link", { name: /^Home/ });
  const from = (await denver.boundingBox())!;
  const to = (await home.boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 });
  await page.mouse.up();
  await expect(grid.getByRole("link").first()).toHaveAccessibleName(/^Denver, 1 of 2/);

  // The order is saved, and the first city is where the app opens.
  await page.reload();
  await expect(grid.getByRole("link").first()).toHaveAccessibleName(/^Denver, 1 of 2/);
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1, name: "Denver" })).toBeVisible();

  // The gear opens style, appearance and units.
  await page.getByRole("link", { name: "All cities" }).click();
  await page.getByRole("button", { name: /^Settings/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Dusk" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-style", "dusk");
  await page.getByRole("dialog").getByRole("button", { name: /°C/ }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Done" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
