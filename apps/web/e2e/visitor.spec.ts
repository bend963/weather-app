import { expect, test, type Page } from "@playwright/test";

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

  await page.getByRole("button", { name: "+ Add" }).click();
  await addLocation(page, "Jackson", /Jackson Hole/, "Jackson Hole");
  await expect(page.getByRole("heading", { level: 1, name: "Jackson Hole" })).toBeVisible({ timeout: 20_000 });

  const nav = page.getByRole("navigation", { name: "Saved locations" });
  await nav.getByRole("link", { name: "Home" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Home" })).toBeVisible();

  // Advanced detail for a day.
  await page.getByRole("list", { name: "Daily forecast" }).getByRole("button").nth(1).click();
  await expect(page.getByRole("dialog")).toContainText("10th percentile");
  await page.getByRole("dialog").getByRole("button", { name: "Close" }).click();

  await page.getByRole("link", { name: /How has this forecast changed/ }).click();
  await expect(page.getByRole("heading", { name: "How the forecast changed" })).toBeVisible();
  await expect(page.getByRole("row", { name: /^High/ })).toBeVisible();
});
