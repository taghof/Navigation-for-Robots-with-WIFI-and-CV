// Put all your lovely jQuery / Javascript goodies right down here.

/* fix the aside so that it takes up the full height available */
$(document).ready(extendAside);
$('img').load(extendAside);

function extendAside() {
  
	if ($('article').innerHeight() > $('aside').innerHeight()) {
		$('aside').css('height', $('article').innerHeight() + 'px')
	}
}