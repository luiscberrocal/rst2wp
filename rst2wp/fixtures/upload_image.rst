:title: Image Uploading
:category: How to
:tags: - Python





Install
=========

test uploading image my flag

.. image:: file:///Users/luiscberrocal/PycharmProjects/rst2wp/rst2wp/fixtures/pa.gif

Changed date and title and category

base.html
----------

.. code-block:: HTML

	{% load i18n %}
	{% get_current_language as LANGUAGE_CODE %}
	
	....
	
    <li>
               <form action="{% url 'set_language' %}" method="post">
                   {% csrf_token %}
                   <div class="form-group">
                       <input name="next" type="hidden" value="{{ no_lang_path }}"/>
                       <select name="language">
                           {% get_language_info_list for LANGUAGES as languages %}
                           {% for language in languages %}
                               <option value="{{ language.code }}"{% if language.code == LANGUAGE_CODE %}
                                       selected="selected"{% endif %}>
                                   {{ language.name_local }} ({{ language.code }})
                               </option>
                           {% endfor %}
                       </select>
                   </div>
                   <input type="submit" class="btn btn-primary" value="{% trans "Go" %}"/>
               </form>
           </li>
	
Add the folloging code :: python

	ugettext = lambda s: s

	LANGUAGES = (
	        ('en', ugettext(u'English')),
	        ('es', ugettext(u'Spanish')),
	)
	LOCALE_PATHS = (
	    join(BASE_DIR,'conf/locale/'),
	)
	