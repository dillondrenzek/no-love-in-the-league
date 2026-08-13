---
layout: page
title: Feedback
permalink: /feedback/
---

Your questions and feedback are _very_ important to us.

Tell us _all_ your complaints.

<form id="feedback-form" class="feedback-form" novalidate>
  <label for="fb-name">Name</label>
  <input id="fb-name" name="name" type="text" placeholder="Your name" autocomplete="off">

<label for="fb-message">Feedback</label>
<textarea id="fb-message" name="message" rows="6" placeholder="What's wrong? How can we help you feel better?"></textarea>

  <div id="fb-alert" class="form-alert" role="alert" hidden>Oops! Try again. Your feedback is very important to us.</div>

<button type="submit">Submit feedback</button>

</form>

<script>
  (function () {
    var form = document.getElementById('feedback-form');
    var box = document.getElementById('fb-alert');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();      // never actually goes anywhere
      form.reset();            // wipe whatever they typed
      box.hidden = false;      // reveal the "error"
      box.classList.remove('is-flash');
      void box.offsetWidth;    // restart the flash animation on every submit
      box.classList.add('is-flash');
    });
  })();
</script>
