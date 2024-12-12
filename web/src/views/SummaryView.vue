<script setup lang="ts">
import { useRouter } from 'vue-router';
import { ref } from 'vue';
import { formState, requestInfo } from '@/store';


const DOCUMENT_TITLE = "Confirm research drive - Archive your research drive"; 
document.title = DOCUMENT_TITLE;

const error = ref("");
const router = useRouter();

function tryContinue() {
    if (formState.isCorrectDrive === null){
        document.title = "Error: " + DOCUMENT_TITLE;
        error.value = "Select Yes if this is research drive you wanted to archive."
    } else {
        if (formState.isCorrectDrive) {
            router.push("/check-details");
        } else {
            router.push("/unable-to-archive")
        }
    }
}

</script>

<template>
    <main>
        <h1 class="app-title">Archive your research drive</h1>
        <section :class="{ error : error }">
            <div class="title-section">
                <h2 class="page-title">Is this the drive you want to archive?</h2>
                <p v-if="error" class="error-msg">{{ error }}</p>
            </div>
        <section class="drive-details-card box">
            <h3 class="h2">Drive information</h3>
            <dl class="details">
                <dt>Name</dt>
                <dl>{{ requestInfo.drive.name }}</dl>
                <dt>Total space</dt>
                <dl>{{ requestInfo.drive.allocated_gb }}GB</dl>
                <dt>Used space</dt>
                <dl>{{ requestInfo.drive.used_gb }}GB</dl>
            </dl>
        </section>
        <form novalidate @submit.prevent="tryContinue()">
        <fieldset>
            <div class="option-list">
                <input name="confirm-drive" type="radio" id="yes-drive" :value="true" v-model="formState.isCorrectDrive">
                <label for="yes-drive">Yes, it is.</label>
                <input name="confirm-drive" type="radio" id="no-drive" :value="false" v-model="formState.isCorrectDrive">
                <label for="no-drive">No, it's not.</label>
            </div>
        </fieldset>
    </form>
    </section>
        <section class="forward-btn">
            
            <a @click.prevent="tryContinue()" class="btn btn-primary">Continue</a>

        </section>
    </main>
</template>

<style scoped>
td {
    padding: 0.5rem;
}
td:first-child {
    font-family: NationalBold;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
}

dt {
    font-family: NationalBold;
}

dt:not(:first-child) {
    margin-top: 1rem;
}

.details {
    margin-top: 1rem;
}

.drive-details-card {
    padding-left: 1rem;
    padding: 1rem;
    margin: 2rem 0;
    width: fit-content;
}

.drive-name {
    font-size: 1.3rem;
    font-weight: bold;
}
</style>