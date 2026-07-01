import { test, expect } from '@playwright/test';

test.describe('Admin Views', () => {
  test.describe('Admin Users', () => {
    test.beforeEach(async ({ page }) => {
      // Login as admin
      await page.goto('/login');
      await page.getByLabel(/email/i).fill('admin@example.com');
      await page.getByLabel(/password/i).fill('adminpassword123');
      await page.getByRole('button', { name: /sign in/i }).click();
      await expect(page).toHaveURL('/');
    });

    test('should show admin section in sidebar for admin users', async ({ page }) => {
      // Admin section should be visible
      await expect(page.getByText(/admin/i, { exact: false })).toBeVisible();
      await expect(page.getByRole('link', { name: /users/i })).toBeVisible();
      await expect(page.getByRole('link', { name: /capture/i })).toBeVisible();
    });

    test('should navigate to user management page', async ({ page }) => {
      await page.getByRole('link', { name: /users/i }).click();

      await expect(page).toHaveURL('/admin/users');
      await expect(page.getByRole('heading', { name: /user management/i })).toBeVisible();
    });

    test('should display users table', async ({ page }) => {
      await page.goto('/admin/users');

      // Should show table headers
      await expect(page.getByRole('columnheader', { name: /email/i })).toBeVisible();
      await expect(page.getByRole('columnheader', { name: /role/i })).toBeVisible();
      await expect(page.getByRole('columnheader', { name: /status/i })).toBeVisible();
    });

    test('should open invite user dialog', async ({ page }) => {
      await page.goto('/admin/users');

      await page.getByRole('button', { name: /invite user/i }).click();

      // Dialog should appear
      await expect(page.getByRole('heading', { name: /invite user/i })).toBeVisible();
      await expect(page.getByPlaceholder(/user@example.com/i)).toBeVisible();
    });

    test('should create invite and show invite URL', async ({ page }) => {
      await page.goto('/admin/users');

      await page.getByRole('button', { name: /invite user/i }).click();

      // Fill invite form
      await page.getByPlaceholder(/user@example.com/i).fill('newuser@example.com');
      await page.getByLabel(/annotator/i).check();
      await page.getByRole('button', { name: /create invite/i }).click();

      // Should show invite URL
      await expect(page.getByText(/invite created/i)).toBeVisible();
      await expect(page.locator('code')).toBeVisible();
    });

    test('should disable/enable user', async ({ page }) => {
      await page.goto('/admin/users');

      // Wait for table to load
      await page.waitForSelector('table tbody tr');

      // Click disable button on first non-admin user
      const disableButton = page.getByRole('button', { name: /disable/i }).first();
      if (await disableButton.isVisible()) {
        await disableButton.click();

        // Status should change to Disabled
        await expect(page.getByText(/disabled/i)).toBeVisible();
      }
    });
  });

  test.describe('Admin Capture', () => {
    test.beforeEach(async ({ page }) => {
      // Login as admin
      await page.goto('/login');
      await page.getByLabel(/email/i).fill('admin@example.com');
      await page.getByLabel(/password/i).fill('adminpassword123');
      await page.getByRole('button', { name: /sign in/i }).click();
      await expect(page).toHaveURL('/');
    });

    test('should navigate to capture page', async ({ page }) => {
      await page.getByRole('link', { name: /capture/i }).click();

      await expect(page).toHaveURL('/admin/capture');
      await expect(page.getByRole('heading', { name: /capture jobs/i })).toBeVisible();
    });

    test('should show capture mode options', async ({ page }) => {
      await page.goto('/admin/capture');

      // Should show radio buttons for capture modes
      await expect(page.getByLabel(/mode a.*search/i)).toBeVisible();
      await expect(page.getByLabel(/mode b.*extract/i)).toBeVisible();
      await expect(page.getByLabel(/foraging/i)).toBeVisible();
    });

    test('should show query input for search/extract modes', async ({ page }) => {
      await page.goto('/admin/capture');

      // Select Mode A
      await page.getByLabel(/mode a.*search/i).check();

      // Should show query input
      await expect(page.getByPlaceholder(/search query/i)).toBeVisible();
    });

    test('should show claim text input for foraging mode', async ({ page }) => {
      await page.goto('/admin/capture');

      // Select Foraging mode
      await page.getByLabel(/foraging/i).check();

      // Should show claim text textarea
      await expect(page.getByPlaceholder(/enter the claim/i)).toBeVisible();
    });

    test('should run capture job', async ({ page }) => {
      await page.goto('/admin/capture');

      // Select Mode A and enter query
      await page.getByLabel(/mode a.*search/i).check();
      await page.getByPlaceholder(/search query/i).fill('test query for capture');

      // Run capture
      await page.getByRole('button', { name: /run capture/i }).click();

      // Should show running state
      await expect(page.getByRole('button', { name: /running/i })).toBeVisible();
    });

    test('should show capture result', async ({ page }) => {
      await page.goto('/admin/capture');

      // Select Mode A and enter query
      await page.getByLabel(/mode a.*search/i).check();
      await page.getByPlaceholder(/search query/i).fill('test query');

      // Run capture and wait for completion
      await page.getByRole('button', { name: /run capture/i }).click();

      // Wait for success box
      await expect(page.getByText(/capture complete/i)).toBeVisible({ timeout: 30000 });
      await expect(page.getByText(/fixture id/i)).toBeVisible();
    });

    test('should show capture mode descriptions', async ({ page }) => {
      await page.goto('/admin/capture');

      // Should show info box with mode descriptions
      await expect(page.getByText(/capture modes/i)).toBeVisible();
      await expect(page.getByText(/unilateral search/i)).toBeVisible();
    });
  });

  test.describe('Non-admin access', () => {
    test.beforeEach(async ({ page }) => {
      // Login as regular annotator
      await page.goto('/login');
      await page.getByLabel(/email/i).fill('annotator@example.com');
      await page.getByLabel(/password/i).fill('annotatorpassword123');
      await page.getByRole('button', { name: /sign in/i }).click();
      await expect(page).toHaveURL('/');
    });

    test('should not show admin section in sidebar for annotators', async ({ page }) => {
      // Admin section should NOT be visible
      await expect(page.getByRole('link', { name: /users/i })).not.toBeVisible();
    });

    test('should redirect to dashboard when accessing admin routes', async ({ page }) => {
      await page.goto('/admin/users');

      // Should redirect to dashboard
      await expect(page).toHaveURL('/');
    });
  });
});
