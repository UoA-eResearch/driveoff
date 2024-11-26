<script lang="ts" setup>
import { formState } from '@/store';
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "How long do your files need to be retained for - Archive your research drive"; 
document.title = DOCUMENT_TITLE;
const error = ref("");
const customPeriod = ref(formState.retentionPeriod);
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
        router.push("/confirm")
    }
    if (error.value !== "") {
        document.title = "Error:" + DOCUMENT_TITLE;
    }
}
</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <section :class="{ error: error}">
            <div class="title-section" >
                <h2 class="page-title">How many years do the files need to be retained for?</h2>
                <p v-if="error" class="error-msg">{{ error }}</p>
            </div>
            <form novalidate @submit.prevent="tryContinue()">
                <div class="form-group">
                    <label for="custom-period">Years after today</label>
                    <input type="number" id="custom-period" v-model="customPeriod">
                </div>
            </form>
        </section>
        <section class="forward-btn"><a @click="tryContinue()" class="btn btn-primary">Continue</a></section>
    </main>
</template>

<style lang="css" scoped>
#custom-period {
    width: 4rem;
}
</style>