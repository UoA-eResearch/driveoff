import { describe, it, expect, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";
import CustomRetentionPeriodView from "../views/CustomRetentionPeriodView.vue";
import { formState } from "../store";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/custom-retention-period", component: CustomRetentionPeriodView },
      { path: "/confirm", component: { template: "<div>confirm</div>" } }
    ]
  });
}

async function mountView() {
  const router = makeRouter();
  router.push("/custom-retention-period");
  await router.isReady();
  return { wrapper: mount(CustomRetentionPeriodView, { global: { plugins: [router] } }), router };
}

describe("CustomRetentionPeriodView", () => {
  beforeEach(() => {
    formState.retentionPeriod = null;
    formState.retentionPeriodJustification = "";
  });

  it("shows an error when retention period is empty", async () => {
    const { wrapper } = await mountView();
    await wrapper.find(".btn-primary").trigger("click");
    expect(wrapper.find(".error-msg").text()).toContain("Enter");
  });

  it("shows an error when retention period is below 6", async () => {
    const { wrapper } = await mountView();
    await wrapper.find("#custom-period").setValue(3);
    await wrapper.find("#custom-period-justification").setValue("some reason");
    await wrapper.find(".btn-primary").trigger("click");
    expect(wrapper.find(".error-msg").text()).toContain("Minimum is 6 years");
  });

  it("shows an error when justification is empty", async () => {
    const { wrapper } = await mountView();
    await wrapper.find("#custom-period").setValue(10);
    await wrapper.find(".btn-primary").trigger("click");
    expect(wrapper.find(".error-msg").text()).toContain("justification");
  });

  it("navigates to /confirm and updates store on valid input", async () => {
    const { wrapper, router } = await mountView();
    await wrapper.find("#custom-period").setValue(10);
    await wrapper.find("#custom-period-justification").setValue("Long-term study");
    await wrapper.find(".btn-primary").trigger("click");
    await flushPromises();
    expect(wrapper.find(".error-msg").exists()).toBe(false);
    expect(formState.retentionPeriod).toBe(10);
    expect(formState.retentionPeriodJustification).toBe("Long-term study");
    expect(router.currentRoute.value.path).toBe("/confirm");
  });
});
