const views = {
  current: {
    endpoint: "/api/current-topics?limit=8&articles_per_topic=5",
    fallbackEndpoint: "/api/hot-topics?days=30&limit=8&articles_per_topic=5"
  }
};

const topicsEl = document.querySelector("#topics");
const topicTemplate = document.querySelector("#topic-template");
const articleTemplate = document.querySelector("#article-template");
const generatedAt = document.querySelector("#generated-at");
const editionDate = document.querySelector("#edition-date");

editionDate.textContent = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
  year: "numeric"
}).format(new Date());

function formatDate(value) {
  if (!value) return "Undated";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function tagLabel(key, value) {
  return `${key.replace("_", " ")}: ${value}`;
}

function tagClassName(key, value) {
  return `tag tag-${key} tag-${key}-${String(value).toLowerCase()}`;
}

function setLoading() {
  topicsEl.innerHTML = '<p class="state">Setting the front page...</p>';
}

function setError() {
  topicsEl.innerHTML = '<p class="state">The edition could not be loaded.</p>';
}

function renderArticle(article) {
  const node = articleTemplate.content.cloneNode(true);
  const link = node.querySelector(".headline");
  const meta = node.querySelector(".meta");
  const summary = node.querySelector(".summary");
  const tags = node.querySelector(".tags");

  link.href = article.url;
  link.textContent = article.title;
  meta.textContent = `${article.source} / ${formatDate(article.published)}`;
  summary.textContent = article.summary || "";
  summary.hidden = !article.summary;

  Object.entries(article.tags).forEach(([key, value]) => {
    if (key === "article_type") return;

    const tag = document.createElement("span");
    tag.className = tagClassName(key, value);
    tag.textContent = tagLabel(key, value);
    tags.appendChild(tag);
  });

  return node;
}

function renderTopics(data) {
  topicsEl.innerHTML = "";

  if (!data.topics.length) {
    topicsEl.innerHTML = '<p class="state">No topics found for this edition.</p>';
    return;
  }

  data.topics.forEach((topic) => {
    const node = topicTemplate.content.cloneNode(true);
    const block = node.querySelector(".topic-block");
    const title = node.querySelector("h3");
    const stats = node.querySelector(".topic-stats");
    const articleList = node.querySelector(".article-list");

    title.textContent = topic.topic;

    const linksButton = document.createElement("button");
    linksButton.className = "topic-links-button";
    linksButton.type = "button";
    linksButton.innerHTML = `<strong>${topic.article_count}</strong> links`;
    linksButton.addEventListener("click", async () => {
      linksButton.disabled = true;

      try {
        const params = new URLSearchParams({
          topic: topic.topic,
          days: data.window_days,
          limit: topic.article_count
        });
        const response = await fetch(`/api/articles?${params}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const articleData = await response.json();
        articleList.innerHTML = "";
        articleData.articles.forEach((article) => {
          articleList.appendChild(renderArticle(article));
        });
        linksButton.innerHTML = `Showing all <strong>${topic.article_count}</strong> links`;
      } catch (error) {
        linksButton.disabled = false;
      }
    });

    stats.appendChild(linksButton);
    stats.insertAdjacentHTML("beforeend", `
      <br>
      <strong>${topic.source_count}</strong> sources<br>
      score ${topic.score}
    `);

    topic.articles.forEach((article) => {
      articleList.appendChild(renderArticle(article));
    });

    topicsEl.appendChild(block);
  });
}

async function loadView(viewName) {
  const view = views[viewName];
  setLoading();

  try {
    let response = await fetch(view.endpoint);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    let data = await response.json();

    if (!data.topics.length && view.fallbackEndpoint) {
      response = await fetch(view.fallbackEndpoint);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
    }

    generatedAt.textContent = `Updated ${formatDate(data.generated_at)}`;
    renderTopics(data);
  } catch (error) {
    generatedAt.textContent = "Offline";
    setError();
  }
}

loadView("current");
