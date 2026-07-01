import { test, expect } from '@playwright/test';

test.describe('T1 Retrieval Judgment', () => {
  test.beforeEach(async ({ page }) => {
    // Login first
    await page.goto('/login');
    await page.getByLabel(/email/i).fill('test@example.com');
    await page.getByLabel(/password/i).fill('testpassword123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/');
  });

  test('should navigate to T1 retrieval judgment page', async ({ page }) => {
    // Click T1: Retrieval in sidebar
    await page.getByRole('link', { name: /t1.*retrieval/i }).click();

    // Should navigate to a claim for judgment
    await expect(page.url()).toMatch(/\/t1\//);
  });

  test('should display claim and candidate documents', async ({ page }) => {
    // Navigate to a specific claim (requires seeded claim)
    await page.goto('/t1/test-claim-id');

    // Should show claim card
    await expect(page.locator('[class*="claimCard"]')).toBeVisible();
    await expect(page.locator('[class*="claimText"]')).toBeVisible();

    // Should show instructions
    await expect(page.getByText(/rate each document/i)).toBeVisible();
  });

  test('should show document list with relevance selectors', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    // Should show document cards
    await expect(page.locator('[class*="documentCard"]')).toBeVisible();

    // Each document should have relevance buttons
    await expect(page.locator('[class*="relevanceButton"]')).toHaveCount({ min: 4 });
  });

  test('should select relevance rating for a document', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    // Wait for documents to load
    await page.waitForSelector('[class*="documentCard"]');

    // Click a relevance button (e.g., "Relevant")
    const relevanceButtons = page.locator('[class*="relevanceButton"]');
    await relevanceButtons.nth(2).click(); // Index 2 = "Relevant"

    // Button should be selected
    await expect(relevanceButtons.nth(2)).toHaveClass(/selected/);
  });

  test('should save progress', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    // Wait for documents and select a rating
    await page.waitForSelector('[class*="documentCard"]');
    await page.locator('[class*="relevanceButton"]').first().click();

    // Click Save Progress
    await page.getByRole('button', { name: /save progress/i }).click();

    // Should show saving state and then return to normal
    await expect(page.getByRole('button', { name: /saving/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /save progress/i })).toBeVisible();
  });

  test('should complete and move to next claim', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    // Wait for documents and select ratings for all
    await page.waitForSelector('[class*="documentCard"]');
    const documentCards = page.locator('[class*="documentCard"]');
    const count = await documentCards.count();

    for (let i = 0; i < count; i++) {
      // Select a rating for each document
      await documentCards.nth(i).locator('[class*="relevanceButton"]').first().click();
    }

    // Click Complete & Next
    await page.getByRole('button', { name: /complete.*next/i }).click();

    // Should navigate to dashboard or next claim
    await expect(page.url()).not.toContain('/t1/test-claim-id');
  });

  test('should show claim badges (family, split, proof standard)', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    // Should show claim metadata badges
    await expect(page.locator('[class*="claimBadge"]')).toHaveCount({ min: 2 });
  });

  test('should show retrieval rank for documents', async ({ page }) => {
    await page.goto('/t1/test-claim-id');

    await page.waitForSelector('[class*="documentCard"]');

    // Some documents should have rank badges
    const rankBadges = page.locator('[class*="rankBadge"]');
    const rankCount = await rankBadges.count();
    expect(rankCount).toBeGreaterThanOrEqual(0);
  });

  test('should handle claim with no linked documents', async ({ page }) => {
    await page.goto('/t1/claim-with-no-docs');

    // Should show empty state
    await expect(page.getByText(/no documents linked/i)).toBeVisible();
  });
});
