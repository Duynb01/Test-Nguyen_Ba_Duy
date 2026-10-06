import { test, expect } from '@playwright/test';

test.describe('End-to-End User Journeys', () => {
  const userA = `usera_${Date.now()}@example.com`;
  const userB = `userb_${Date.now()}@example.com`;
  const password = 'password123';

  test('Scenario 1: Happy Path - Register, Create Todo, Complete Todo, Logout', async ({ page }) => {
    await page.goto('/');

    // 1. Register
    await page.click('text=Sign up');
    await page.fill('input[type="email"]', userA);
    await page.fill('input[type="password"]', password);
    await page.fill('input[placeholder="Confirm password"]', password);
    await page.click('button:has-text("Sign up")');

    // Wait for redirect to login page (assuming simple redirect on successful registration)
    await expect(page.locator('text=Sign in to your account')).toBeVisible();

    // 2. Login
    await page.fill('input[type="email"]', userA);
    await page.fill('input[type="password"]', password);
    await page.click('button:has-text("Sign in")');

    // Wait for the app to load
    await expect(page.locator('h1:has-text("Todos")')).toBeVisible();

    // 3. Create Todo
    const todoTitle = 'My First E2E Todo';
    const todoDesc = 'This is created by Playwright';
    await page.fill('input[placeholder="What needs to be done?"]', todoTitle);
    await page.fill('input[placeholder="Description (optional)"]', todoDesc);
    await page.click('button:has-text("Add Todo")');

    // Wait for the todo to appear
    const todoItem = page.locator(`text=${todoTitle}`);
    await expect(todoItem).toBeVisible();

    // 4. Complete Todo
    // The checkbox is usually the first input inside the todo item's container
    // We can locate the item by looking for the label/text, then finding the checkbox near it
    const todoContainer = page.locator('div', { hasText: todoTitle }).locator('..');
    const checkbox = todoContainer.locator('input[type="checkbox"]');
    
    // Check it
    await checkbox.check();
    
    // Expect it to be checked
    await expect(checkbox).toBeChecked();

    // 5. Logout
    await page.click('button:has-text("Sign out")');
    await expect(page.locator('text=Sign in to your account')).toBeVisible();
  });

  test('Scenario 2: Data Isolation - User B cannot see User A\'s todos', async ({ page }) => {
    await page.goto('/');

    // 1. Register User B
    await page.click('text=Sign up');
    await page.fill('input[type="email"]', userB);
    await page.fill('input[type="password"]', password);
    await page.fill('input[placeholder="Confirm password"]', password);
    await page.click('button:has-text("Sign up")');

    await expect(page.locator('text=Sign in to your account')).toBeVisible();

    // 2. Login User B
    await page.fill('input[type="email"]', userB);
    await page.fill('input[type="password"]', password);
    await page.click('button:has-text("Sign in")');

    await expect(page.locator('h1:has-text("Todos")')).toBeVisible();

    // 3. Verify Todo List is empty (should not see User A's todo)
    // The text 'My First E2E Todo' should NOT be visible
    await expect(page.locator('text=My First E2E Todo')).not.toBeVisible();
    await expect(page.locator('text=No todos yet. Add one above!')).toBeVisible();
  });
});
