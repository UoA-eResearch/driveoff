<script lang="ts" setup>
import { createSubmissionApiV1SubmissionPost } from '@/client';
import { getProjectMembers, getProjectOwners, membersToString } from '@/models/helpers';
import { formState, requestInfo } from '@/store';
import { useRouter } from 'vue-router';

const DOCUMENT_TITLE = "Check your answers - Archive your research drive";
document.title = DOCUMENT_TITLE;

const router = useRouter();
const projectOwners = membersToString(getProjectOwners(requestInfo.project.members ?? []));
const projectMembers = membersToString(getProjectMembers(requestInfo.project.members ?? []));

const projectTitle = requestInfo.project.title;
const projectDescription = requestInfo.project.description;

async function submit(){
    const dataClassification = formState.dataClassification;
    const retentionPeriod = formState.retentionPeriod;
    if (dataClassification === null || retentionPeriod === null ){
        // Form is not yet complete!
        // This should not happen.
        return;
    }
    const req = await createSubmissionApiV1SubmissionPost({
        body: {
            drive_name: requestInfo.drive.name,
            retention_period_years: retentionPeriod,
            retention_period_justification: formState.retentionPeriodJustification,
            data_classification: dataClassification,
        }
    });
    if (req.data) {
        router.push("/finish");
    } else if (req.error && req.response.status === 409) {
        router.push("/already-archived");
    } else {
        router.push("/service-error");
    }
}
</script>

<template>
  <h1 class="app-title">
    Archive your research drive
  </h1>
  <div class="title-section">
    <h2 class="page-title">
      Check your answers before sending your request
    </h2>
  </div>
  <h3 class="h2">
    Project details
  </h3>
  <table>
    <colgroup>
      <col class="part-name-col">
      <col>
    </colgroup>
    <tbody>
      <tr>
        <td>Project name</td>
        <td>{{ projectTitle }}</td>
      </tr>
      <tr>
        <td>Project description</td>
        <td> {{ projectDescription }}</td>
      </tr>
      <tr>
        <td>Project owner</td>
        <td>{{ projectOwners }}</td>
      </tr>
      <tr>
        <td>Project members</td>
        <td>{{ projectMembers }}</td>
      </tr>
      <tr>
        <td>Department</td>
        <td>{{ requestInfo.project.division }}</td>
      </tr>
    </tbody>
  </table>

  <h3 class="h2">
    Archive details
  </h3>
  <table>
    <colgroup>
      <col class="part-name-col">
      <col>
    </colgroup>
    <tbody>
      <tr>
        <td>Data classification</td>
        <td>{{ formState.dataClassification }}</td>
      </tr>
      <tr>
        <td>Retention period</td>
        <td>{{ formState.retentionPeriod }} years from today</td>
      </tr>
      <tr>
        <td>Retention period justification</td>
        <td>{{ formState.retentionPeriodJustification }}</td>
      </tr>
    </tbody>
  </table>
  <h3 class="h2">
    Send this request
  </h3>
  By sending this request you are confirming that the details are correct and you wish to archive this drive.
  <section class="forward-btn">
    <button
      class="btn btn-primary"
      @click="submit()"
    >Submit</button>
  </section>
</template>

<style scoped>
td {
    padding: 0.5rem;
    border-bottom: 1px solid var(--brand-light);
    
}
td:first-child {
    font-family: "Inter", sans-serif;
    font-weight: 700;
}

td:last-of-type {
    text-align: end;
}

.forward-btn {
    display: flex;
    gap: 1rem;
}

table {
    width: 100%;
    margin-bottom: 2rem;
    table-layout: fixed;;
}

.part-name-col {
    width: 30%;
}
</style>