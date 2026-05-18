# Outreach to PA Forestry Association

Send to: **thePFA@paforestry.org**
CC (optional, secondary): **info@paforestry.org**
Subject: **Big Trees of the Northeast — request to mirror PA Big Trees data with attribution**

## Background context (for you, not for the email)

- PA Big Trees is run by the Pennsylvania Forestry Association (PFA), a 501(c)(3) non-profit founded in 1886 — the nation's oldest state forestry organization.
- Their public JSON API is at `https://www.pabigtrees.com/trees` and images at `https://pabigtrees.com/treeImages/`. robots.txt permits all paths with a 20-second crawl delay.
- We have already mirrored the data and ~2,500 photos locally for the demo build. The site is not yet pushed to a public URL.
- The site adds prominent credit (hero callout with donation CTA) and links every PA tree's modal back to the official `pabigtrees.com` page.

## Draft email

Subject: Big Trees of the Northeast — request to mirror PA Big Trees data with attribution

Hi PA Forestry Association,

I'm Stephen Stirling, a data journalist. I'm building a small public project that ranks and presents the biggest trees in New Jersey and Pennsylvania side-by-side, with photos and how to find the ones that are publicly accessible. The NJ data comes from NJ DEP's Big and Heritage Trees Program. The Pennsylvania portion uses the public JSON API and image archive on pabigtrees.com.

Before I make the project public, I want to ask permission and make sure my use respects your work.

What I've built:
- A static page (no ads, no tracking) that loads a one-time snapshot of your /trees API and a resized copy of the photos referenced in each record. The site lives in a GitHub repo and would be served from a personal GitHub Pages URL.
- Every PA tree on the page links back to `https://www.pabigtrees.com/tree-listings/{id}`.
- The Pennsylvania tab has a prominent credit callout in the header that names PFA, links to your site, and links to your donation page on Stripe.
- The methodology section asks readers who find the page useful to donate to PFA.

What I'd like to ask:
1. Are you comfortable with this mirror as described? If you'd prefer I hot-link the photos from pabigtrees.com instead of mirroring them, or use a different attribution wording, I'm happy to adjust.
2. Is there a coordinator or photographer credit you'd like surfaced on each PA tree's detail view?
3. Anything else you'd want — a banner during a fundraising drive, a specific link target, a phrase you'd like attribution to use?

If the answer to (1) is "please don't," I will take down the Pennsylvania tab. I do not want to extract value from PFA's volunteer work without your blessing. The project will work fine with just the NJ data while we sort it out.

A few details for transparency:
- The mirror is one-time and was throttled to roughly 1 request per second.
- I resize photos to 900px wide JPEG and strip all EXIF metadata before hosting.
- The page is open source; happy to share the GitHub link if useful.

Thank you for the program. PA Big Trees is a remarkable thing — preserving 50+ years of careful, volunteer-driven work on big trees in PA.

Stephen Stirling
stephenstirling@gmail.com
[optional: link to GitHub repo once public]

## What to do based on their response

- **Yes, go ahead** → push and launch. Keep the credit callout where it is.
- **Yes, but hot-link photos** → delete `photos/pa/`, change `photoUrl(...)` in app.js to return `https://pabigtrees.com/treeImages/{img_location}` directly, document the dependency in the README.
- **Yes, but credit each photographer** → request the photographer field if available in API; surface in modal.
- **No / please take down** → remove the PA tab from the site, leave NJ standalone, keep `scripts/fetch_pa_*.py` in repo but not run them.
- **No response after 2 weeks** → safest move is to either (a) launch with the current visible-credit setup and respond promptly to any complaint, or (b) hold and try a second outreach. Editorial call.
