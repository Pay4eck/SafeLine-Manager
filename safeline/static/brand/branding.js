(() => {
  "use strict";

  const script = document.getElementById("safeline-branding");
  if (!script) return;

  const brand = script.dataset;
  const exactText = new Map([
    ["Hiddify", brand.fullName],
    ["Hiddify Manager", brand.manager],
    ["HiddifyManager", brand.manager],
    ["Hiddify Panel", brand.manager],
    ["Powered by hiddify.com", brand.manager],
    ["Powered By Hiddify.com", brand.manager],
    ["Install Hiddify Application", `Install ${brand.fullName}`],
  ]);

  const replaceTitle = () => {
    document.title = document.title
      .replace(/HiddifyManager/g, brand.manager)
      .replace(/Hiddify Manager/g, brand.manager)
      .replace(/Hiddify Panel/g, brand.manager)
      .replace(/Hiddify \| Panel/g, brand.fullName)
      .replace(/\|\s*(?:DEV|\d+(?:\.\d+){1,3})\s*$/, `| ${brand.version}`);
  };

  const replaceExactTextNodes = (root) => {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    nodes.forEach((node) => {
      const parent = node.parentElement;
      if (!parent || ["SCRIPT", "STYLE", "CODE", "PRE"].includes(parent.tagName)) return;
      const trimmed = node.nodeValue.trim();
      if (exactText.has(trimmed)) {
        node.nodeValue = node.nodeValue.replace(trimmed, exactText.get(trimmed));
      } else if (/©\s*\d{4}\s+Hiddify\b/.test(trimmed)) {
        node.nodeValue = node.nodeValue.replace(/Hiddify\b/, brand.manager);
      } else if (/^Hiddify:\s/.test(trimmed)) {
        node.nodeValue = node.nodeValue.replace(/^Hiddify/, brand.manager);
      } else if (/^Hiddify$/.test(trimmed) && parent.matches("h1, h2, h3")) {
        node.nodeValue = node.nodeValue.replace("Hiddify", brand.manager);
      }
    });
  };

  const rewriteChrome = (root) => {
    root.querySelectorAll(".brand-text").forEach((element) => {
      element.textContent = element.textContent
        .replace(/HiddifyManager/g, brand.manager)
        .replace(/Hiddify Manager/g, brand.manager)
        .replace(/^Hiddify\b/g, brand.manager);
    });

    root.querySelectorAll("#splash_screen img, #main-sidebar > a img, a.brand-link img").forEach((image) => {
      image.src = brand.icon;
      image.alt = `${brand.product} logo`;
    });

    root.querySelectorAll("#main-sidebar > a .ltr, footer.main-footer .badge").forEach((version) => {
      version.textContent = brand.version;
    });

    root.querySelectorAll("a[href]").forEach((anchor) => {
      const href = anchor.href.toLowerCase();
      const managerLink = href.includes("github.com/hiddify/hiddify-manager");
      const upstreamSocial =
        href.includes("t.me/hiddify") ||
        href.includes("youtube.com/@hiddify") ||
        href.includes("twitter.com/intent/follow?screen_name=hiddify_com") ||
        href === "https://hiddify.com/";

      if (managerLink && !anchor.dataset.safelineAttribution) {
        anchor.href = brand.repository;
      } else if (upstreamSocial) {
        const listItem = anchor.closest("li");
        (listItem || anchor).hidden = true;
      }
    });

    const splashLink = root.querySelector("#splash_screen a");
    if (splashLink) splashLink.href = brand.repository;
  };

  const ensureAttribution = () => {
    const footer = document.querySelector("footer.main-footer");
    if (!footer || footer.querySelector("[data-safeline-attribution]")) return;
    const attribution = document.createElement("a");
    attribution.dataset.safelineAttribution = "true";
    attribution.href = brand.upstream;
    attribution.target = "_blank";
    attribution.rel = "noreferrer";
    attribution.className = "ml-2 text-muted";
    attribution.textContent = "Based on Hiddify Manager";
    footer.prepend(attribution);
  };

  const apply = (root = document) => {
    replaceTitle();
    replaceExactTextNodes(root);
    rewriteChrome(root);
    ensureAttribution();
  };

  apply();
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) apply(node);
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
