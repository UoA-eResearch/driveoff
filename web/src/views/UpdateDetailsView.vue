<script lang="ts" setup>
import { ref } from "vue";
import { store } from "../store"
import { useRouter } from "vue-router";

const DOCUMENT_TITLE = "Update project title and description - Archive your research drive"; 
document.title = DOCUMENT_TITLE;

const title = ref(store.project?.title || "");
const titleError = ref("");
const description = ref(store.project?.description || "");
const descriptionError = ref("");
const router = useRouter();

function tryContinue() {
    title.value = title.value.trim();
    description.value = description.value.trim();
    if (title.value === ""){
        titleError.value = "Enter a title for the project."
    } else {
        titleError.value = "";
    }
    if (description.value === "") {
        descriptionError.value = "Enter a description for the project."
    } else {
        descriptionError.value = "";
    }
    if (titleError.value !== "" || descriptionError.value !== "") {
        // If there's an error, do not advance to the next page.
        document.title = "Error: " + DOCUMENT_TITLE;
        return;
    }
    // Go to the next page
    router.push("/");
}
</script>
<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <div class="title-section">
            <h2 class="page-title">Update project title and description</h2>
        </div>
        <form novalidate>
            <div class="form-group" :class="{ error : titleError }">
                <label for="project-title" class="h2">Title</label>
                <p v-if="titleError" class="error-msg">{{ titleError }}</p>
                <input type="text" id="project-title" v-model="title">
            </div>
            <div class="form-group" :class="{ error : descriptionError }">
                <label for="project-description" class="h2">Description</label>
                <p v-if="descriptionError" class="error-msg">{{ descriptionError }}</p>
                <textarea id="project-description" v-model="description"></textarea>
            </div>
            <!-- <div class="form-group">
                <label for=""
            </div> -->
        </form>
        <section class="forward-btn">
            <a @click.prevent="tryContinue()" class="btn btn-primary">Continue</a>
        </section>
    </main>

</template>

<style scoped>
    input[type=text], textarea {
        border: 2px solid gray;
        padding:0.35rem;
        margin-top: 0.5rem;
    }

    textarea {
        min-height: 10rem;
    }

    .form-group {
        display: flex;
        flex-direction: column;
        margin-top: 1.5rem;
    }
</style>