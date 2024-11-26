<script setup lang="ts">
import { formState } from '@/store';
import { ref, type Ref } from 'vue';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "Retention period - Archive your research drive";
document.title = DOCUMENT_TITLE;
const initialValue: "custom" | number | null = formState.isRetentionPeriodCustom ? "custom" : formState.retentionPeriod;
const period = ref(initialValue);
const error = ref("");
const router = useRouter();

function tryContinue() {
    if (period.value === null) {
        error.value = "Choose the right retention period for the files on your drive.";
    } else if (period.value === "custom") {
        formState.isRetentionPeriodCustom = true;
        formState.retentionPeriod = null;
        error.value = "";
        router.push("/custom-retention-period");
    } else {
        // Period is one of the predefined retention periods.
        formState.isRetentionPeriodCustom = false;
        formState.retentionPeriod = period.value;
        error.value = "";
        router.push("/confirm");
    }
}

</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <section :class="{ error : error }">
            <div class="title-section">
                <h2 class="page-title">How long do your files need to be retained?</h2>
                <p v-if="error" class="error-msg">{{ error }}</p>
                <p>See <a class="btn-link" target="_blank" href="https://research-hub.auckland.ac.nz/managing-research-data/ethics-integrity-and-compliance/research-data-retention">Research data retention</a> for full guidance.</p>
            </div>
            <form novalidate class="option-list">
                <input name="confirm-drive" type="radio" id="rp-6y" value="6" v-model="period">
                <label for="rp-6y">6 years from today</label>
                <input name="confirm-drive" type="radio" id="rp-10y" value="10" v-model="period">
                <label for="rp-10y">10 years from today</label>
                <input name="confirm-drive" type="radio" id="rp-20y" value="20" v-model="period">
                <label for="rp-20y">20 years from today</label>
                <input name="confirm-drive" type="radio" id="rp-26y" value="26" v-model="period">
                <label for="rp-26y">26 years from today</label>
                <input name="confirm-drive" type="radio" id="rp-custom" value="custom" v-model="period">
                <label for="rp-custom">Something else</label>
            </form>
        </section>
        <section class="forward-btn">
            <a @click="tryContinue()"class="btn btn-primary">Continue</a>
        </section>
    </main>
</template>