/* Small, dependency-free interactions for StockPilot. */
document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebar-overlay");
  const toggle = document.getElementById("menu-toggle");

  function closeSidebar() {
    sidebar?.classList.remove("open");
    overlay?.classList.remove("show");
  }

  toggle?.addEventListener("click", () => {
    sidebar?.classList.toggle("open");
    overlay?.classList.toggle("show");
  });
  overlay?.addEventListener("click", closeSidebar);

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  document.querySelectorAll(".needs-validation").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      form.classList.add("was-validated");
    });
  });

  document.querySelectorAll("[data-transaction-form]").forEach((form) => setupTransactionForm(form));
});

function setupTransactionForm(form) {
  const tbody = form.querySelector("[data-line-items]");
  const template = form.querySelector("[data-line-template]");
  const addButton = form.querySelector("[data-add-line]");
  const totalElement = form.querySelector("[data-grand-total]");
  const priceAttribute = form.dataset.priceAttribute;

  const formatMoney = (amount) => `₹${Number(amount || 0).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

  function updateLine(line, setSuggestedPrice = false) {
    const product = line.querySelector(".line-product");
    const option = product.options[product.selectedIndex];
    const quantity = parseFloat(line.querySelector(".line-quantity").value) || 0;
    const priceInput = line.querySelector(".line-price");
    const stockCell = line.querySelector(".available-stock");
    if (option?.value) {
      stockCell.textContent = Number(option.dataset.stock || 0).toLocaleString("en-IN");
      if (setSuggestedPrice || !priceInput.value) priceInput.value = option.dataset[priceAttribute] || "";
    } else {
      stockCell.textContent = "—";
    }
    const price = parseFloat(priceInput.value) || 0;
    line.querySelector(".line-subtotal").textContent = formatMoney(quantity * price);
    updateTotal();
  }

  function updateTotal() {
    let total = 0;
    tbody.querySelectorAll(".transaction-line").forEach((line) => {
      const quantity = parseFloat(line.querySelector(".line-quantity").value) || 0;
      const price = parseFloat(line.querySelector(".line-price").value) || 0;
      total += quantity * price;
    });
    totalElement.textContent = formatMoney(total);
  }

  function bindLine(line) {
    line.querySelector(".line-product").addEventListener("change", () => updateLine(line, true));
    line.querySelector(".line-quantity").addEventListener("input", () => updateLine(line));
    line.querySelector(".line-price").addEventListener("input", () => updateLine(line));
    line.querySelector(".remove-line").addEventListener("click", () => {
      const lines = tbody.querySelectorAll(".transaction-line");
      if (lines.length === 1) {
        line.querySelector(".line-product").value = "";
        line.querySelector(".line-quantity").value = "";
        line.querySelector(".line-price").value = "";
        updateLine(line);
      } else {
        line.remove();
        updateTotal();
      }
    });
  }

  tbody.querySelectorAll(".transaction-line").forEach(bindLine);
  addButton.addEventListener("click", () => {
    const fragment = template.content.cloneNode(true);
    const newLine = fragment.querySelector(".transaction-line");
    tbody.appendChild(fragment);
    bindLine(tbody.lastElementChild);
  });
  updateTotal();
}
