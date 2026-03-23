<script lang="ts" setup>
import { formState } from '@/store';
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "How long do your files need to be retained for - Archive your research drive"; 
document.title = DOCUMENT_TITLE;
const error = ref("");
const customPeriod = ref(formState.retentionPeriod);
const customPeriodJustification = ref("");
const router = useRouter();

function tryContinue(){
    if (customPeriod.value === null) {
        error.value = "Enter how many years your files need to be retained for. For example, 15.";
    } else if (customPeriod.value <= 0 || typeof customPeriod.value !== "number") {
        error.value = "Enter a positive number of years your files need to be retained for. For example, 15.";
    } else if (!Number.isInteger(customPeriod.value)) {
        error.value = "Enter a whole number of years your files need to be retained for. For example, 15";
    } else {
        error.value = "";
        formState.retentionPeriod = customPeriod.value;
        formState.retentionPeriodJustification = customPeriodJustification.value;
        router.push("/confirm")
    }
    if (error.value !== "") {
        document.title = "Error:" + DOCUMENT_TITLE;
    }
}
</script>

<template>
  <main>
    <h1 class="app-title">
      Archive your research drive
    </h1>
    <section :class="{ error: error}">
      <div class="title-section">
        <h2 class="page-title">
          How many years do the files need to be retained for?
        </h2>
        <p
          v-if="error"
          class="error-msg"
        >
          {{ error }}
        </p>
      </div>
      <form
        novalidate
        @submit.prevent="tryContinue()"
      >
        <div class="form-group">
          <label for="custom-period">Years from today</label>
          <input
            id="custom-period"
            v-model="customPeriod"
            type="number"
          >
        </div>
        <div class="form-group">
          <label for="custom-period-justification">Justification</label>
          <textarea
            id="custom-period-justification"
            v-model="customPeriodJustification"
          ></textarea>
          <p class="helper-text">Provide a justification for the retention period you have selected. 
            For example, "Research data involving children must be retained until participants are 
            16 years old, plus 10 years."</p>
        </div>
      </form>
    </section>
    <section class="forward-btn">
      <a
        class="btn btn-primary"
        @click="tryContinue()"
      >Continue</a>
    </section>
  </main>
</template>

<style lang="css" scoped>
#custom-period {
    width: 4rem;
}
.helper-text {
    font-size: 0.9rem;
    font-style: italic;
}
</style>