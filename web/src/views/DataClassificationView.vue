<script setup lang="ts">
import { formState } from '@/store';
import { ref } from 'vue';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "Data classification - Archive your research drive";
document.title = DOCUMENT_TITLE;

const dataClassification = ref(formState.dataClassification);
const error = ref("");
const router = useRouter();
function tryContinue() {
    if (!dataClassification.value) {
        error.value = "Select the right data classification for the files in your drive."
        document.title = "Error: " + DOCUMENT_TITLE;
        return;
    } else {
        formState.dataClassification = dataClassification.value;
        error.value = "";
        router.replace("retention-period");
    }
}
</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <section :class="{ error : error }">
            <div class="title-section">
                <h2 class="page-title">What is the data classification for the files in your drive?</h2>
                <p v-if="error" class="error-msg">{{ error }}</p>
                <p>See <a href="https://research-hub.auckland.ac.nz/article/research-data-classification" target="_blank">Research data classification standard</a> for full guidance.</p>
            </div>
            <form @submit.prevent="tryContinue()" class="option-list">
                <input name="dc" type="radio" value="Public" id="public-dc" v-model="dataClassification">
                <label for="public-dc">Public</label>
                <input name="dc" type="radio" value="Internal" id="internal-dc" v-model="dataClassification">
                <label for="internal-dc">Internal
                </label>
                <input name="dc" type="radio" value="Sensitive" id="sensitive-dc" v-model="dataClassification">
                <label for="sensitive-dc" >Sensitive
                </label>
                <input name="dc" type="radio" value="Restricted" id="restricted-dc" v-model="dataClassification">
                <label for="restricted-dc">Restricted
                </label>
            </form>
        </section>
            <section class="forward-btn">
        <a @click="tryContinue()" class="btn btn-primary">Continue</a>
            </section>
    </main>
</template>